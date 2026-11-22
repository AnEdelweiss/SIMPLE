from unittest.mock import MagicMock, patch

import opensilexClientToolsPython as silex
import pytest
import requests
import urllib3

from simple.auth import (
    check_connection_internet,
    connexion,
    deconnexion,
    get_login,
    is_connected,
)

# Assure-toi d'adapter les imports à l'arborescence exacte de ton projet
from simple.erreurs import AuthenticationError, NetworkError


class TestAuth:
    # ==========================================
    # TESTS POUR CHECK_CONNECTION_INTERNET
    # ==========================================

    @patch("simple.auth.requests.get")
    def test_check_connection_internet_success(self, mock_get):
        """Teste que la fonction passe silencieusement si internet fonctionne"""
        # Le mock ne lève aucune exception (simule un code 200 OK)
        check_connection_internet()
        # On vérifie que la requête a bien été tentée
        assert mock_get.called is True

    @patch("simple.auth.requests.get")
    def test_check_connection_internet_failure(self, mock_get):
        """Teste qu'une erreur réseau lève bien la NetworkError personnalisée"""
        # On simule un timeout ou une coupure réseau
        mock_get.side_effect = requests.ConnectionError("Pas de connexion")

        with pytest.raises(NetworkError) as error_info:
            check_connection_internet()

        assert "No internet access :/" in str(error_info.value)

    # ==========================================
    # TESTS POUR IS_CONNECTED
    # ==========================================

    def test_is_connected_true(self):
        """Teste que la fonction repère bien l'en-tête d'autorisation"""
        mock_client = MagicMock()
        mock_client.default_headers = {"Authorization": "Bearer token123"}

        assert is_connected(mock_client) is True

    def test_is_connected_false(self):
        """Teste le renvoi False quand il n'y a pas d'autorisation"""
        mock_client = MagicMock()
        mock_client.default_headers = {}  # Pas d'autorisation

        assert is_connected(mock_client) is False

    # ==========================================
    # TESTS POUR DECONNEXION
    # ==========================================

    @patch("simple.auth.silex.AuthenticationApi")
    def test_deconnexion_success(self, MockAuthApi):
        """Logout is really called and the token is removed"""
        mock_client = MagicMock()
        mock_client.default_headers = {"Authorization": "Bearer token123"}

        result = deconnexion(mock_client)

        assert result is True
        MockAuthApi.assert_called_once_with(mock_client)
        MockAuthApi.return_value.logout.assert_called_once()
        assert "Authorization" not in mock_client.default_headers

    @patch("simple.auth.silex.AuthenticationApi")
    def test_deconnexion_empty_body_counts_as_success(self, MockAuthApi):
        """Client fails to parse the server's empty logout reply: still a success,
        and the temporary Accept header must not leak."""
        import json

        mock_client = MagicMock()
        mock_client.default_headers = {"Authorization": "Bearer token123"}
        seen = {}

        def fake_logout(**kwargs):
            seen["accept"] = mock_client.default_headers.get("Accept")
            raise json.JSONDecodeError("Expecting value", "", 0)

        MockAuthApi.return_value.logout.side_effect = fake_logout

        assert deconnexion(mock_client) is True
        assert seen["accept"] == "application/json"
        assert mock_client.default_headers == {}

    @patch("simple.auth.silex.AuthenticationApi")
    def test_deconnexion_failure(self, MockAuthApi):
        """Server error: no exception, header still removed, returns False"""
        mock_client = MagicMock()
        mock_client.default_headers = {"Authorization": "Bearer token123"}
        MockAuthApi.return_value.logout.side_effect = silex.rest.ApiException(
            status=500, reason="Server error"
        )

        result = deconnexion(mock_client)

        assert result is False
        assert "Authorization" not in mock_client.default_headers

    @patch("simple.auth.silex.AuthenticationApi")
    def test_deconnexion_network_error(self, MockAuthApi):
        mock_client = MagicMock()
        mock_client.default_headers = {"Authorization": "Bearer token123"}
        MockAuthApi.return_value.logout.side_effect = urllib3.exceptions.MaxRetryError(
            None, "/security/logout"
        )

        assert deconnexion(mock_client) is False
        assert "Authorization" not in mock_client.default_headers

    @patch("simple.auth.silex.AuthenticationApi")
    def test_deconnexion_no_header(self, MockAuthApi):
        """No token: nothing to do, no server call"""
        mock_client = MagicMock()
        mock_client.default_headers = {}

        assert deconnexion(mock_client) is True
        MockAuthApi.return_value.logout.assert_not_called()

    # ==========================================
    # TESTS POUR CONNEXION
    # ==========================================

    @patch("simple.auth.deconnexion")
    def test_connexion_success(self, mock_deconnexion):
        """Teste que la connexion appelle bien le SDK avec les bons paramètres"""
        mock_client = MagicMock()
        login_dict = {
            "host": "https://fake.url",
            "identifier": "user",
            "password": "pwd",
        }

        result = connexion(login_dict, mock_client)

        assert result is True
        # Vérifie qu'on a bien déconnecté d'abord
        mock_deconnexion.assert_called_once_with(mock_client)
        # Vérifie qu'on passe bien le dictionnaire déballé (**)
        mock_client.connect_to_opensilex_ws.assert_called_once_with(**login_dict)

    @patch("simple.auth.deconnexion")
    def test_connexion_api_error_json(self, mock_deconnexion):
        """Teste l'extraction du message d'erreur JSON renvoyé par OpenSilex"""
        mock_client = MagicMock()
        login_dict = {"host": "https://fake.url"}

        # On reproduit la chaîne exacte (assez laide) que l'API renvoie quand on se trompe de mdp
        faux_message_erreur = 'HTTP response body: {"result": {"message": "Invalid credentials provided"}}'
        mock_client.connect_to_opensilex_ws.side_effect = Exception(faux_message_erreur)

        with pytest.raises(AuthenticationError) as error_info:
            connexion(login_dict, mock_client)

        # On vérifie que notre fonction a bien décortiqué le JSON pour extraire le vrai message
        assert "Invalid credentials provided" in str(error_info.value)

    # ==========================================
    # TESTS POUR GET_LOGIN (INTERFACE)
    # ==========================================

    @patch("simple.auth.Prompt.ask")
    @patch("simple.auth.IntPrompt.ask")
    def test_get_login(self, mock_int_ask, mock_ask):
        """Teste la collecte des informations de connexion via Rich"""
        # On simule l'utilisateur qui tape '1' (UH)
        mock_int_ask.return_value = 1

        # side_effect permet de donner les réponses successives : d'abord le nom, puis le mot de passe
        mock_ask.side_effect = ["mon_adresse@mail.com", "mon_mot_de_passe_secret"]

        login_dict = get_login()

        assert login_dict["host"] == "https://phis.emphasis.fedcloud.eu/uh/rest"
        assert login_dict["identifier"] == "mon_adresse@mail.com"
        assert login_dict["password"] == "mon_mot_de_passe_secret"
