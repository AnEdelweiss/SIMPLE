class SimpleBaseException(Exception):
    """Classe de base pour toutes les exceptions de l'application SIMPLE."""



class NetworkError(SimpleBaseException):
    """Levée quand la connect internet ou l'API échoue."""



class AuthenticationError(SimpleBaseException):
    """Levée pour les problèmes de login, de mots de passe ou de tokens."""



class DataImportError(SimpleBaseException):
    """Levée quand les données du fichier MIAPPE ou tabulaire sont manquantes ou invalides."""



class ImportCancelled(SimpleBaseException):
    """Raised when the user cancels a running import."""


class ConfigurationError(SimpleBaseException):
    """Levée quand un fichier ou un dossier attendu est introuvable sur la machine."""

