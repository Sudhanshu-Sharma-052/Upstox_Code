import secrets

class UpstoxLoginManager:

    @staticmethod
    def generate_state():

        return secrets.token_urlsafe(32)