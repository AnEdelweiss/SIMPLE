import json

import opensilexClientToolsPython as silex
import requests
import urllib3

from simple.errors import AuthenticationError, NetworkError
from simple.logging_setup import logger
from simple.ui import IntPrompt, Prompt, Table, console

# Initiatialisation des différentes instances
INSTANCES = {
    "https://opensilex.org/sandbox/rest": "Sandbox",
    "https://phis.emphasis.fedcloud.eu/uh/rest": "Helsinki/UH",
    "https://opensilex.org/demo2/rest": "test1.5.1",
}


def get_login():
    console.print("[cyan]Connection :[/cyan]")
    login = {}
    instance_urls = list(INSTANCES.keys())
    instance_names = list(INSTANCES.values())

    table = Table(title="Available instances", show_header=False)
    table.add_column("Index", style="cyan")
    table.add_column("Name", style="green")
    for index, name in enumerate(instance_names):
        table.add_row(str(index), name)
    console.print(table)
    while True:
        instance_index = IntPrompt.ask(
            f"[green]\\[+][/green][cyan]On which instance would you like to log in (0-{len(instance_names) - 1})[/cyan]"
        )
        if 0 <= instance_index <= len(instance_names) - 1:
            login["host"] = instance_urls[instance_index]
            break
        else:
            console.print(
                f"[red][bold]Please type a number between [white]0[/white] and [white]{len(instance_names) - 1}[/white][/red][/bold]"
            )
    if instance_index == 0:
        login["identifier"] = "guest@opensilex.org"
        login["password"] = "guest"
    else:
        login["identifier"] = Prompt.ask(
            f"[green]\\[+][/green]  [cyan]Username/mail on [/cyan] [green]{INSTANCES[login['host']]}[/green]"
        )
        login["password"] = Prompt.ask(
            "[green]\\[+][/green] [cyan] Password[/cyan] [red](it is invisible for security reasons)[/red]",
            password=True,
        )
    return login


# On deconnecte le client avant toute nouvelle connect
def logout(api_client) -> bool:
    """Logout from the server and always clear the local auth header.

    Returns True if there was no token or the server logout succeeded, False
    if the server logout failed (API error, network error, timeout). The local
    "Authorization" header is removed in every case and no exception is raised,
    so callers (e.g. connect) can proceed regardless of the return value.
    """
    headers = api_client.default_headers
    if "Authorization" not in headers:
        return True
    # The generated client's logout() crashes client-side with KeyError('Accept')
    # unless an Accept header is set, and the server answers with an empty body
    # that the client then fails to parse as JSON (JSONDecodeError). Both are
    # client quirks: with Accept set, a JSONDecodeError means the server replied 2xx.
    added_accept = "Accept" not in headers
    if added_accept:
        headers["Accept"] = "application/json"
    try:
        silex.AuthenticationApi(api_client).logout(_request_timeout=10)
        return True
    except json.JSONDecodeError:
        return True
    except (silex.rest.ApiException, urllib3.exceptions.HTTPError, OSError) as e:
        logger.warning(f"Server logout failed: {e!r}")
        console.print(
            f"[yellow]Warning: server logout failed ({e}); local session cleared.[/yellow]"
        )
        return False
    finally:
        headers.pop("Authorization", None)
        if added_accept:
            headers.pop("Accept", None)


# Je verifie que l'utilisateur a accès à internet.
def check_connection_internet():
    with console.status("checking internet access..."):
        # initializing URL
        logger.info("Checking internet access...")
        url = "https://www.wikipedia.org/"
        timeout = 5
        try:
            # requesting URL
            requests.get(url, timeout=timeout)
            logger.info("User has internet !")
            return
        # catching exception
        except (requests.ConnectionError, requests.Timeout):
            logger.error("No internet access :/")
            raise NetworkError("No internet access :/")


# Check rapide de la connect
def is_connected(api_client) -> bool:
    return (
        api_client is not None
        and "Authorization" in api_client.default_headers
    )


def _authentication_error_from_api(
    exc: silex.rest.ApiException,
) -> AuthenticationError:
    """Turn an OpenSILEX ``ApiException`` into the historical user message.

    ``ApiException.body`` holds the server response body. When it is JSON with
    a ``result.message`` field that message is used verbatim; when it cannot
    be decoded the old "impossible to decode" message is kept. An exception
    without a body keeps the old raw-text fallback.
    """
    error_str = str(exc)
    if exc.body:
        try:
            error_data = json.loads(exc.body)
            message = (
                f"User authentication failed :{error_data['result']['message']}"
            )
        except (TypeError, ValueError, KeyError, IndexError):
            message = f"error is impossible to decode :{error_str}"
    else:
        message = f"error : User authentication failed :{error_str}"
    logger.error(message)
    return AuthenticationError(message)


# Connexion et gestion des erreurs de connect
def connect(login, api_client) -> bool:
    logout(api_client)
    try:
        api_client.connect_to_opensilex_ws(
            **login
        )  # Connexion avec le login reçu via la CLI
        logger.info(f"User Sucessfully connected to : {login["host"]}")
        return True

    except silex.rest.ApiException as e:
        # Newer client revisions may let the API exception through directly.
        raise _authentication_error_from_api(e) from e

    except (urllib3.exceptions.HTTPError, OSError) as e:
        message = f"error : User authentication failed :{e}"
        logger.error(message)
        raise AuthenticationError(message) from e

    except Exception as e:
        # Intentional broad catch, kept because the pinned OpenSILEX client is
        # quirky: connect_to_opensilex_ws() catches silex.rest.ApiException and
        # re-raises a plain Exception("Connection to OpenSilex failed: ..."),
        # keeping the original only as __context__. It also raises a plain
        # Exception("Identifier not defined") for missing credentials. Unwrap
        # the original API error when present so the message can use .body.
        cause = e.__context__
        if isinstance(cause, silex.rest.ApiException):
            auth_error = _authentication_error_from_api(cause)
        else:
            message = f"error : User authentication failed :{e}"
            logger.error(message)
            auth_error = AuthenticationError(message)
        raise auth_error from e
