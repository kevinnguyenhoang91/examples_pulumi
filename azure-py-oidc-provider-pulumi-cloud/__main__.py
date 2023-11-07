import pulumi
from pulumi_azure_native import resources, aad, authorization, managedidentity
import pulumi_azuread as azuread
from pulumi_azure import core
import yaml
import random

'''
For the purposes of this example, a random number
will be generated and assigned to parameter values that
require unique values. This should be removed in favor
of providing unique naming conventions where required.
'''
number = random.randint(1000,9999)

issuer = "https://api.pulumi.com/oidc"

# Retrieve local Pulumi configuration
pulumi_config = pulumi.Config()
audience = pulumi.get_organization()
env_name = pulumi_config.require("environmentName")

# Retrieve local Azure configuration
azure_config = authorization.get_client_config()
az_subscription = azure_config.subscription_id
tenant_id = azure_config.tenant_id

# Create a Microsoft Entra Application
application = azuread.Application(
    f'pulumi-oidc-app-reg-{number}',
    display_name='pulumi-environments-oidc-app',
    sign_in_audience='AzureADMyOrg',
)

# Create Federated Credentials
subject = f"pulumi:environments:org:{audience}:env:{env_name}"

federated_identity_credential = azuread.ApplicationFederatedIdentityCredential("federatedIdentityCredential",
    application_object_id=application.object_id,
    display_name=f"pulumi-env-oidc-fic-{number}",
    description="Federated credentials for Pulumi ESC",
    audiences=[audience],
    issuer=issuer,
    subject=subject
)

# Create a Service Principal
service_principal = azuread.ServicePrincipal('myserviceprincipal', application_id=application.application_id)

# Assign the 'Contributor' role to the Service principal at the scope specified
CONTRIBUTOR=f"/subscriptions/{az_subscription}/providers/Microsoft.Authorization/roleDefinitions/b24988ac-6180-42a0-ab88-20f7382dd24c"

role_assignment = authorization.RoleAssignment('myroleassignment',
                                 role_definition_id=CONTRIBUTOR,
                                 principal_id=service_principal.id,
                                 principal_type="ServicePrincipal",
                                 scope=f"/subscriptions/{az_subscription}",
                                 )

print("OIDC configuration complete!")
print("Copy and paste the following template into your Pulumi ESC environment:")
print("--------")

def create_yaml_structure(args):
    application_id, tenant_id, subscription_id = args
    return {
        'values': {
            'azure': {
                'login': {
                    'fn::open::azure-login': {
                        'clientId': application_id,
                        'tenantId': tenant_id,
                        'subscriptionId': subscription_id,
                        'oidc': True
                    }
                }
            },
            'environmentVariables': { 
                'ARM_USE_OIDC': 'true',
                'ARM_CLIENT_ID': '${azure.login.clientId}',
                'ARM_TENANT_ID': '${azure.login.tenantId}',
                # Currently need both OIDC_REQUEST_TOKEN and OIDC_TOKEN. 
                # See: https://github.com/pulumi/pulumi-azure-native/issues/2868
                'ARM_OIDC_REQUEST_TOKEN': '${azure.login.oidc.token}',
                'ARM_OIDC_TOKEN': '${azure.login.oidc.token}',
                'ARM_SUBSCRIPTION_ID': '${azure.login.subscriptionId}',
                'ARM_OIDC_REQUEST_URL': 'https://api.pulumi.com/oidc'
            }
        }
    }

def print_yaml(args):
    yaml_structure = create_yaml_structure(args)
    yaml_string = yaml.dump(yaml_structure, sort_keys=False)
    print(yaml_string)

pulumi.Output.all(application.application_id, tenant_id, az_subscription).apply(print_yaml)