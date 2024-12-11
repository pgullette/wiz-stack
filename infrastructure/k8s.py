import pulumi
import json
import pulumi_kubernetes as k8s
import pulumi_aws as aws
import pulumi_std as std
import pulumi_tls as tls
import pulumi_random as random
import pulumi_docker_build as docker_build
from eks import eks_cluster, node_group
from ecr import ecr_repository
from urllib.parse import quote

# Get AWS caller identity
caller_identity = aws.get_caller_identity()

# Load Pulumi configuration and needed variables
config = pulumi.Config()
git_repo_url = config.require("git_repo_url")
es_config = config.require_object("external_secrets")
internal_domain = config.require("internal_domain")
db_instance_name = config.require("db_instance")
web_app_config = config.require_object("web_app")

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
    kubeconfig=kubeconfig,
    opts=(pulumi.ResourceOptions(depends_on=node_group))
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

# Helm Chart
external_secrets_chart = k8s.helm.v4.Chart(
    es_config.get("helm_chart"),
    chart=es_config.get("helm_chart"),
    version=es_config.get("helm_chart_version"),
    repository_opts=k8s.helm.v4.RepositoryOptsArgs(
        repo=es_config.get("helm_repo")
    ),
    namespace=namespace.metadata["name"],
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
    web_app_config.get("name"),
    metadata={"name": web_app_config.get("name")},
    opts=pulumi.ResourceOptions(provider=k8s_provider)
)

# Create random password for the db
random_password = random.RandomPassword("dbPassword",
    length=16,
    special=True,
    keepers={
        "keeper": "change-me-to-change-password"
    }
)

# DB connection details secret
db_secret = aws.secretsmanager.Secret(
    web_app_config.get("postgres_secret"),
    name=web_app_config.get("postgres_secret"),
    description="PostgreSQL connection details",
    tags={
        "Environment": "Production"
    }
)

# Create a Secrets Manager secret version with the generated secret string
secret_version = aws.secretsmanager.SecretVersion("dbSecretVersion",
    secret_id=db_secret.id,
    secret_string=pulumi.Output.json_dumps({
        "username": web_app_config.get("name"),
        "password": random_password.result,
        "host": f"{db_instance_name}.{internal_domain}",
        "port": 5432,
        "db": web_app_config.get("name")
    })
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
        "values": [namespace.metadata.name.apply(lambda ns_name: f"system:serviceaccount:{ns_name}:{ns_name}-sa")]
    }],
    "principals": [{
        "identifiers": [open_id_connect_provider.arn],
        "type": "Federated"
    }]
}])

web_app_role = aws.iam.Role("web-app-irsa",
    assume_role_policy=assume_role_policy.json,
    name="web-app-irsa")

# Create IAM policy for the service account allowing access to web-app* secrets
iam_policy = aws.iam.Policy("web-app-allow-secrets-manager-policy",
    policy=json.dumps({
        "Version": "2012-10-17",
        "Statement": [
            {
                "Effect": "Allow",
                "Action": "secretsmanager:GetSecretValue",
                "Resource": f"arn:aws:secretsmanager:{aws.config.region}:{caller_identity.account_id}:secret:{web_app_config.get("name")}*"
            }
        ]
    })
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
        "name": pulumi.Output.concat(namespace.metadata.name, "-sa"),
        "namespace": namespace.metadata.name,
        "annotations": {
            # Annotations for IRSA
            "eks.amazonaws.com/role-arn": web_app_role.arn
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
    opts=pulumi.ResourceOptions(
        provider=k8s_provider,
        depends_on=external_secrets_chart
    )
)

# Create externalsecret resource to generate the db connection url from aws secret
postgres_external_secret = k8s.apiextensions.CustomResource("postgres-external-secret",
    api_version="external-secrets.io/v1beta1",
    kind="ExternalSecret",
    metadata={
        "name": "postgres-url-secret",
        "namespace": namespace.metadata.name
    },
    spec={
        "secretStoreRef": {
            "kind": "SecretStore",
            "name": "aws"
        },
        "target": {
            "name": "postgres-url-secret",
            "template": {
                "data": {
                    "postgres-url": "postgres://{{ .username }}:{{ .password | urlquery }}@{{ .host }}:{{ .port }}/{{ .db }}"
                },
            },
        },
        "data": [
            {
                "secretKey": "username", 
                "remoteRef": {
                    "key": db_secret.name,
                    "property": "username"
                }
            },
            {
                "secretKey": "password",
                "remoteRef": {
                    "key": db_secret.name,
                    "property": "password"
                }
            },
            {
                "secretKey": "host", 
                "remoteRef": {
                    "key": db_secret.name,
                    "property": "host"
                }
            },
            {
                "secretKey": "port", 
                "remoteRef": {
                    "key": db_secret.name,
                    "property": "port"
                }
            },
            {
                "secretKey": "db", 
                "remoteRef": {
                    "key": db_secret.name,
                    "property": "db"
                }
            }
        ]
    },
    opts=pulumi.ResourceOptions(
        provider=k8s_provider,
        depends_on=external_secrets_chart
    )
)

# Build the web app from Dockerfile
auth_token = aws.ecr.get_authorization_token()

my_image = docker_build.Image("my-image",
    cache_from=[{
        "registry": {
            "ref": ecr_repository.repository_url.apply(lambda repository_url: f"{repository_url}:cache")
        },
    }],
    cache_to=[{
        "registry": {
            "image_manifest": True,
            "oci_media_types": True,
            "ref": ecr_repository.repository_url.apply(lambda repository_url: f"{repository_url}:cache")
        },
    }],
    context={
        "location": "../ultra-tic/"
    },
    platforms=[docker_build.Platform.LINUX_AMD64],
    push=True,
    registries=[{
        "address": ecr_repository.repository_url,
        "password": auth_token.password,
        "username": auth_token.user_name
    }],
    tags=[ecr_repository.repository_url.apply(lambda repository_url: f"{repository_url}:latest")])

# Create overly permissive service account for deployment to use
service_account = k8s.core.v1.ServiceAccount(
    "i-have-the-power",
    metadata={
        "name": "i-have-the-power",
        "namespace": namespace.metadata.name
    },
    opts=pulumi.ResourceOptions(provider=k8s_provider)
)

# Create a ClusterRoleBinding to grant cluster-admin role to the ServiceAccount
cluster_role_binding = k8s.rbac.v1.ClusterRoleBinding(
    "my-cluster-role-binding",
    metadata={
        "name": "my-cluster-role-binding"
    },
    role_ref={
        "apiGroup": "rbac.authorization.k8s.io",
        "kind": "ClusterRole",
        "name": "cluster-admin"
    },
    subjects=[
        {
            "kind": "ServiceAccount",
            "name": service_account.metadata["name"],
            "namespace": namespace.metadata.name
        }
    ],
    opts=pulumi.ResourceOptions(provider=k8s_provider)
)

# Web app deployment
app_labels = {"app": web_app_config.get("name")}

deployment = k8s.apps.v1.Deployment(
    web_app_config.get("name"),
    metadata={
        "name": web_app_config.get("name"),
        "namespace": namespace.metadata.name
    },
    spec={
        "replicas": 1,
        "selector": {
            "matchLabels": app_labels
        },
        "template": {
            "metadata": {
                "labels": app_labels
            },
            "spec": {
                "serviceAccountName": service_account.metadata.name,
                # "initContainers": [{
                #     "name": f"{web_app_config.get("name")}-init",
                #     "image": my_image.ref,
                #     "command": ["npx", "--y", "prisma", "migrate", "deploy"],
                #     "env": [{
                #         "name": "DATABASE_URL",
                #         "valueFrom": {
                #             "secretKeyRef": {
                #                 "name": "postgres-url-secret",
                #                 "key": "postgres-url"
                #             }
                #         }
                #     }]
                # }],
                "containers": [{
                    "name": web_app_config.get("name"),
                    "image": my_image.ref,
                    "env": [{
                        "name": "DATABASE_URL",
                        "valueFrom": {
                            "secretKeyRef": {
                                "name": "postgres-url-secret",
                                "key": "postgres-url"
                            }
                        }
                    }]
                }]
            }
        }
    },
    opts=pulumi.ResourceOptions(provider=k8s_provider)
)

# Create a LoadBalancer Service for the Deployment
service = k8s.core.v1.Service(
    web_app_config.get("name"),
    metadata=k8s.meta.v1.ObjectMetaArgs(
        name=web_app_config.get("name"),
        namespace=namespace.metadata.name
    ),
    spec=k8s.core.v1.ServiceSpecArgs(
        selector=app_labels,
        ports=[
            k8s.core.v1.ServicePortArgs(
                port=80,
                target_port=web_app_config.get("target_port"),
                protocol="TCP"
            )
        ],
        type="LoadBalancer"  # Expose via LoadBalancer
    ),
    opts=pulumi.ResourceOptions(
        provider=k8s_provider,
        depends_on=deployment
    )
)

# Export the LoadBalancer's DNS name or IP
dns_name = service.status.apply(
    lambda status: status.load_balancer.ingress[0].hostname
    if status.load_balancer.ingress and "hostname" in status.load_balancer.ingress[0]
    else status.load_balancer.ingress[0].ip
    if status.load_balancer.ingress
    else None
)

pulumi.export("web-app lb dns", dns_name)