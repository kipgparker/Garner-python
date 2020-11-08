import ast
import datetime
import re

import boto3
from envs import env
from jose import JWTError, jwt
import requests
from getpass import getpass

from aws_srp import AWSSRP
from exceptions import TokenVerificationException

from config import config

import uuid


class Auth:
    
    def __init__(self, username=None, private_key=None, password=None):
        
        self.user_pool_id = config["aws_user_pools_id"]
        self.user_pool_region = config["aws_cognito_region"]
        self.client_id = config["aws_user_pools_web_client_id"]
        
        self.username = username
        self.private_key = private_key
        
        self.refresh_token = None
        self.token_type = None
        self.access_token = None
        self.pool_jwk = None
        self.id_token = None
        
        self.client = boto3.client("cognito-idp", region_name=self.user_pool_region)
        
        self.authenticate(password)
        
    def authenticate(self, password):
        """
        Authenticate the user using the SRP protocol
        :param password: The user's passsword
        :return:
        """
        if not password:
            print("Enter Password")
        aws = AWSSRP(
            username=self.username,
            password=(password if password else getpass("Password:")),
            pool_id=self.user_pool_id,
            client_id=self.client_id,
            client=self.client,
        )
        tokens = aws.authenticate_user('Password:')
        
        
        print("Authenticated")
        self.verify_token(tokens["AuthenticationResult"]["IdToken"], "id_token", "id")
        self.refresh_token = tokens["AuthenticationResult"]["RefreshToken"]
        self.verify_token(
            tokens["AuthenticationResult"]["AccessToken"], "access_token", "access"
        )
        self.id_token: refresh_response['AuthenticationResult']['IdToken']
        self.token_type = tokens["AuthenticationResult"]["TokenType"]
        self.access_token = tokens['AuthenticationResult']['AccessToken']
        
    def get_keys(self):
        if self.pool_jwk:
            return self.pool_jwk

        # Check for the dictionary in environment variables.
        pool_jwk_env = env("COGNITO_JWKS", {}, var_type="dict")
        if pool_jwk_env:
            self.pool_jwk = pool_jwk_env
        # If it is not there use the requests library to get it
        else:
            self.pool_jwk = requests.get(
                "https://cognito-idp.{}.amazonaws.com/{}/.well-known/jwks.json".format(
                    self.user_pool_region, self.user_pool_id
                )
            ).json()
        return self.pool_jwk

    def get_key(self, kid):
        keys = self.get_keys().get("keys")
        key = list(filter(lambda x: x.get("kid") == kid, keys))
        return key[0]
    
    def verify_token(self, token, id_name, token_use):
        kid = jwt.get_unverified_header(token).get("kid")
        unverified_claims = jwt.get_unverified_claims(token)
        token_use_verified = unverified_claims.get("token_use") == token_use
        if not token_use_verified:
            raise TokenVerificationException("Your {} token use could not be verified.")
        hmac_key = self.get_key(kid)
        try:
            verified = jwt.decode(
                token,
                hmac_key,
                algorithms=["RS256"],
                audience=unverified_claims.get("aud"),
                issuer=unverified_claims.get("iss"),
            )
        except JWTError:
            raise TokenVerificationException("Your {} token could not be verified.")
        setattr(self, id_name, token)
        return verified
    
    def check_token(self, renew=True):
        """
        Checks the exp attribute of the access_token and either refreshes
        the tokens by calling the renew_access_tokens method or does nothing
        :param renew: bool indicating whether to refresh on expiration
        :return: bool indicating whether access_token has expired
        """
        if not self.access_token:
            raise AttributeError('Access Token Required to Check Token')
        now = datetime.datetime.now()
        dec_access_token = jwt.get_unverified_claims(self.access_token)

        if now > datetime.datetime.fromtimestamp(dec_access_token['exp']):
            expired = True
            if renew:
                self.renew_access_token()
        else:
            expired = False
        return expired
    
    def renew_access_token(self):
        """
        Sets a new access token on the User using the refresh token.
        """
        auth_params = {'REFRESH_TOKEN': self.refresh_token}
        #self._add_secret_hash(auth_params, 'SECRET_HASH')
        refresh_response = self.client.initiate_auth(
            ClientId=self.client_id,
            AuthFlow='REFRESH_TOKEN',
            AuthParameters=auth_params,
        )
        
        status_code = refresh_response.get(
            'HTTPStatusCode',
            refresh_response['ResponseMetadata']['HTTPStatusCode']
        )
        
        if status_code == 200:
            self.access_token = refresh_response['AuthenticationResult']['AccessToken']
            self.id_token: refresh_response['AuthenticationResult']['IdToken']
            self.token_type: refresh_response['AuthenticationResult']['TokenType']