import pulumi
import json
import pulumi_kubernetes as k8s
import pulumi_aws as aws
import pulumi_std as std
import pulumi_tls as tls
from eks import eks_cluster

# Get AWS caller identity
caller_identity = aws.get_caller_identity()

# Load Pulumi configuration and needed variables
config = pulumi.Config()
git_repo_url = config.require("git_repo_url")
es_config = config.require_object("external_secrets")

# Generate the kubeconfig
kubeconfig = pulumi.Output.all(
    cluster_name=eks_cluster.name,
    cluster_endpoint=eks_cluster.endpoint,
    cluster_certificate=eks_cluster.certificate_authority.apply(lambda ca: ca["data"])
).apply(lambda args: json.dumps({
    "apiVersion": "v1",
    "clusters": [{
        "cluster": {
            "server": args["cluster_endpoint"],
            "certificate-authority-data": args["cluster_certificate"]
        },
        "name": "kubernetes"
    }],
    "contexts": [{
        "context": {
            "cluster": "kubernetes",
            "user": "aws"
        },
        "name": "aws"
    }],
    "current-context": "aws",
    "kind": "Config",
    "users": [{
        "name": "aws",
        "user": {
            "exec": {
                "apiVersion": "client.authentication.k8s.io/v1beta1",
                "command": "aws",
                "args": [
                    "eks",
                    "get-token",
                    "--cluster-name",
                    args["cluster_name"]
                ]
            }
        }
    }]
}))

# Add k8s bootstrap components to cluster
k8s_provider = k8s.Provider(
    "k8s-provider",
    kubeconfig=kubeconfig
)

########################################
########## External secrets ############
########################################
# Namespace
namespace = k8s.core.v1.Namespace(
    "external-secrets",
    metadata={"name": "external-secrets"},
    opts=pulumi.ResourceOptions(provider=k8s_provider)
)

# Service Account
# service_account = k8s.core.v1.ServiceAccount(
#     "external-secrets-sa",
#     metadata={
#         "name": "external-secrets-sa",
#         "namespace": namespace.metadata["name"],
#         "annotations": {
#             # Annotations for IRSA
#             "eks.amazonaws.com/role-arn": external_secrets_role.arn,
#         },
#     },
#     opts=pulumi.ResourceOptions(provider=k8s_provider)
# )

# Helm Chart
external_secrets_chart = k8s.helm.v4.Chart(
    es_config.get("helm_chart"),
    chart=es_config.get("helm_chart"),
    version=es_config.get("helm_chart_version"),
    repository_opts=k8s.helm.v4.RepositoryOptsArgs(
        repo=es_config.get("helm_repo")
    ),
    namespace=namespace.metadata["name"],
    values={
        # Use the custom service account
        # "serviceAccount": {
        #     "create": False,  # Disable default service account creation
        #     "name": service_account.metadata["name"],
        # },
    },
    opts=pulumi.ResourceOptions(
        provider=k8s_provider,
        depends_on=[namespace]
    )
)

########################################
############## Web App #################
########################################
# Namespace
namespace = k8s.core.v1.Namespace(
    "web-app",
    metadata={"name": "web-app"},
    opts=pulumi.ResourceOptions(provider=k8s_provider)
)

# Set up IRSA role using eks oidc provider
oidc_issuer = eks_cluster.identities.apply(lambda identities: tls.get_certificate_output(url=identities[0].oidcs[0].issuer))

open_id_connect_provider = aws.iam.OpenIdConnectProvider("oidc-provider",
    client_id_lists=["sts.amazonaws.com"],
    thumbprint_lists=[oidc_issuer.certificates[0].sha1_fingerprint],
    url=oidc_issuer.url)

assume_role_policy = aws.iam.get_policy_document_output(statements=[{
    "actions": ["sts:AssumeRoleWithWebIdentity"],
    "effect": "Allow",
    "conditions": [{
        "test": "StringEquals",
        "variable": std.replace_output(text=open_id_connect_provider.url,
            search="https://",
            replace="").apply(lambda invoke: f"{invoke.result}:sub"),
        "values": [namespace.metadata.name.apply(lambda ns_name: f"system:serviceaccount:{ns_name}:{ns_name}-sa")],
    }],
    "principals": [{
        "identifiers": [open_id_connect_provider.arn],
        "type": "Federated",
    }],
}])

web_app_role = aws.iam.Role("web-app-irsa",
    assume_role_policy=assume_role_policy.json,
    name="web-app-irsa")

# Create IAM policy for the service account
iam_policy = aws.iam.Policy("web-app-allow-secrets-manager-policy",
    policy=json.dumps({
        "Version": "2012-10-17",
        "Statement": [
            {
                "Effect": "Allow",
                "Action": "secretsmanager:GetSecretValue",
                "Resource": f"arn:aws:secretsmanager:{aws.config.region}:{caller_identity.account_id}:secret:web-app*"
            }
        ]
    }),
)

# Attach the policy to the irsa role
aws.iam.RolePolicyAttachment("irsa-policy-attachment",
    role=web_app_role.name,
    policy_arn=iam_policy.arn
)

# Service Account
service_account = k8s.core.v1.ServiceAccount(
    "web-app-sa",
    metadata={
        "name": "web-app-sa",
        "namespace": namespace.metadata["name"],
        "annotations": {
            # Annotations for IRSA
            "eks.amazonaws.com/role-arn": web_app_role.arn,
        },
    },
    opts=pulumi.ResourceOptions(provider=k8s_provider)
)

# AWS SecretStore
css = k8s.yaml.v2.ConfigGroup(
    "aws-css",
    objs=[{
        "apiVersion": "external-secrets.io/v1beta1",
        "kind": "SecretStore",
        "metadata": {
            "name": "aws",
            "namespace": namespace.metadata.name
        },
        "spec": {
            "provider": {
                "aws": {
                    "service": "SecretsManager",
                    "region": aws.config.region,
                    "auth": {
                        "jwt": {
                            "serviceAccountRef": {
                                "name": service_account.metadata.name
                            }
                        }
                    }
                }
            }
        }
    }],
    opts=pulumi.ResourceOptions(provider=k8s_provider)
)

# Install kapp-controller to the cluster
# kapp_controller = k8s.yaml.v2.ConfigFile(
#     "kapp-controller",
#     file="https://github.com/carvel-dev/kapp-controller/releases/latest/download/release.yml",
#     opts=pulumi.ResourceOptions(provider=k8s_provider)
# )

# Install kapp bootstrap prereqs to the cluster
# kapp_prereqs = k8s.yaml.v2.ConfigFile(
#     "kapp-prereqs",
#     file="kapp-prereqs/k8s-resources.yaml",
#     opts=pulumi.ResourceOptions(
#         provider=k8s_provider,
#         depends_on=kapp_controller
#     )
# )

# # Kapp app
# kapp_app = f"""
# apiVersion: kappctrl.k14s.io/v1alpha1
# kind: App
# metadata:
#     name: bootstrap-app
#     namespace: kapp-apps
# spec:
#     serviceAccountName: kapp-apps-sa
#     fetch:
#     - git:
#         url: {git_repo_url}
#         ref: origin/main
#         subPath: kapp

#     template:
#     - ytt: {{}}

#     deploy:
#     - kapp: {{}}
# """

# # Install kapp app to finish bootstrapping the cluster
# kapp_bootstrap = k8s.yaml.v2.ConfigGroup(
#     "kapp-bootstrap",
#     yaml=kapp_app,
#     opts=pulumi.ResourceOptions(
#         provider=k8s_provider, 
#         depends_on=kapp_prereqs
#     )
# )