import boto3
import uuid
from ..config import config

class Storage():
    def __init__(self, Auth):
        
        self.cognito_client =  boto3.client('cognito-identity', region_name=config["aws_cognito_region"])
        
        self.id_token = Auth.id_token
        
        self.identity_id = self.get_identity_id(self.id_token)
        
        self.aws_credentials = self.get_credentials(
            self.identity_id, self.id_token
        )
        
        self.s3_client = boto3.client(
            's3',
            aws_access_key_id=self.aws_credentials['AccessKeyId'],
            aws_secret_access_key=self.aws_credentials['SecretKey'],
            aws_session_token=self.aws_credentials['SessionToken'],
        )
        

    def get_identity_id(self, id_token):
        provider_name = "cognito-idp.{}.amazonaws.com/{}".format(config["aws_cognito_region"],
                                                                 config["aws_user_pools_id"])
        creds = self.cognito_client.get_id(
            IdentityPoolId=config["aws_cognito_identity_pool_id"],
            Logins={provider_name: id_token}
        )
        return creds['IdentityId']

    def get_credentials(self, identity_id, id_token):
        provider_name = "cognito-idp.{}.amazonaws.com/{}".format(config["aws_cognito_region"],
                                                                 config["aws_user_pools_id"])
        creds = self.cognito_client.get_credentials_for_identity(
            IdentityId=identity_id,
            Logins={provider_name: id_token},
        )
        return creds['Credentials']
    
    def get_prefix(self):
        return '/'.join(["protected", self.identity_id])
        
    def upload_file(self, file_path):
        prefix = self.get_prefix()
        key = str(uuid.uuid4()) + '.' + file_path.split('.')[-1]
        key = '/'.join([prefix, key])
        return self.s3_client.upload_file(file_path, config["aws_user_files_s3_bucket"], key)