import pulumi
import pulumi_aws as aws
import json
from network import private_subnet_a, private_subnet_b, public_subnet_a, public_subnet_b, vpc

# Retrieve the Amazon Linux 2 AMI for the us-east-1 region
ami = aws.ec2.get_ami(
    most_recent=True,
    owners=["amazon"],  # Only consider Amazon-owned AMIs
    filters=[
        {"name": "name", "values": ["amzn2-ami-hvm-*-x86_64-gp2"]},  # Amazon Linux 2 AMIs
    ]
)

# Security Group for EKS Nodes
node_sg = aws.ec2.SecurityGroup("node-sg",
    vpc_id=vpc.id,
    egress=[
        {
            "protocol": "-1",
            "from_port": 0,
            "to_port": 0,
            "cidr_blocks": ["0.0.0.0/0"]
        }
    ],
    tags={"Name": "node-sg"})

# Add ingress rule to allow inter security group access
aws.ec2.SecurityGroupRule(
    "allow-sg-ingress-access",
    type="ingress",
    from_port=0,
    to_port=0,
    protocol="-1",
    security_group_id=node_sg.id,
    source_security_group_id=node_sg.id
)

# Create EKS Role
eks_role = aws.iam.Role(
    "eks-role",
    assume_role_policy=json.dumps({
        "Version": "2012-10-17",
        "Statement": [
            {
                "Action": "sts:AssumeRole",
                "Effect": "Allow",
                "Principal": {"Service": "eks.amazonaws.com"}
            }
        ]
    }),
    tags={"Name": "eks-role"}
)

# Attach EKS cluster policy to EKS Role
aws.iam.RolePolicyAttachment("eks-cluster-eks-role",
    role=eks_role.name,
    policy_arn="arn:aws:iam::aws:policy/AmazonEKSClusterPolicy"
)

# Create EKS Cluster
eks_cluster = aws.eks.Cluster(
    "eks-cluster",
    role_arn=eks_role.arn,
    vpc_config=aws.eks.ClusterVpcConfigArgs(
        subnet_ids=[private_subnet_a.id, private_subnet_b.id],
        security_group_ids=[node_sg.id]
    ),
    tags={"Name": "eks-cluster"}
)

# Add CoreDNS add-on
coredns_addon = aws.eks.Addon(
    "coreDNSAddon",
    cluster_name=eks_cluster.name,
    addon_name="coredns",
    resolve_conflicts_on_update="OVERWRITE",  # Options: OVERWRITE, NONE, PRESERVE
)

# Add kube-proxy add-on
kube_proxy_addon = aws.eks.Addon(
    "kubeProxyAddon",
    cluster_name=eks_cluster.name,
    addon_name="kube-proxy",
    resolve_conflicts_on_update="OVERWRITE",
)

# Add VPC CNI add-on
vpc_cni_addon = aws.eks.Addon(
    "vpcCNIAddon",
    cluster_name=eks_cluster.name,
    addon_name="vpc-cni",
    resolve_conflicts_on_update="OVERWRITE",
)

# Add EKS Pod Identity Agent add-on
eks_pod_identity_agent = aws.eks.Addon(
    "eks-pod-identity-agent",
    cluster_name=eks_cluster.name,
    addon_name="eks-pod-identity-agent",
    resolve_conflicts_on_update="OVERWRITE"
)

# Create Node Role
node_role = aws.iam.Role(
    "eks-node-role",
    assume_role_policy=json.dumps({
        "Version": "2012-10-17",
        "Statement": [
            {
                "Action": "sts:AssumeRole",
                "Effect": "Allow",
                "Principal": {"Service": "ec2.amazonaws.com"}
            }
        ]
    }),
    tags={"Name": "eks-node-role"}
)

# Attach policies to the node role
# SSM
aws.iam.RolePolicyAttachment("node-role-ssm-managed",
    role=node_role.name,
    policy_arn="arn:aws:iam::aws:policy/AmazonSSMManagedInstanceCore"
)

aws.iam.RolePolicyAttachment("eks-worker-node-policy",
    role=node_role.name,
    policy_arn="arn:aws:iam::aws:policy/AmazonEKSWorkerNodePolicy"
)

aws.iam.RolePolicyAttachment("eks-cni-policy",
    role=node_role.name,
    policy_arn="arn:aws:iam::aws:policy/AmazonEKS_CNI_Policy"
)

# ECR read-only access policy
aws.iam.RolePolicyAttachment("ecr-readonly-policy",
    role=node_role.name,
    policy_arn="arn:aws:iam::aws:policy/AmazonEC2ContainerRegistryReadOnly"
)

# Create Node Group
node_group = aws.eks.NodeGroup(
    "eks-node-group",
    cluster_name=eks_cluster.name,
    node_role_arn=node_role.arn,
    subnet_ids=[private_subnet_a.id, private_subnet_b.id],
    scaling_config=aws.eks.NodeGroupScalingConfigArgs(
        desired_size=2,
        max_size=2,
        min_size=1
    ),
    instance_types=["t3.medium"]
)

# Load Balancer for EKS
load_balancer = aws.lb.LoadBalancer(
    "eks-load-balancer",
    internal=False,
    security_groups=[node_sg.id],
    subnets=[public_subnet_a.id, public_subnet_b.id]
)

# Export cluster info
pulumi.export("eks_cluster_name", eks_cluster.name)
pulumi.export("eks_cluster_endpoint", eks_cluster.endpoint)