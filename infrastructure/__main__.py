import pulumi
import pulumi_aws as aws

# VPC
vpc = aws.ec2.Vpc(
    "main-vpc",
    cidr_block="10.0.0.0/16",
    enable_dns_support=True,
    enable_dns_hostnames=True,
    tags={"Name": "main-vpc"},
)

# Public Subnet
public_subnet = aws.ec2.Subnet(
    "public-subnet",
    vpc_id=vpc.id,
    cidr_block="10.0.1.0/24",
    map_public_ip_on_launch=True,
    availability_zone="us-east-1a",
    tags={"Name": "public-subnet"},
)

# Private Subnet
private_subnet = aws.ec2.Subnet(
    "private-subnet",
    vpc_id=vpc.id,
    cidr_block="10.0.2.0/24",
    availability_zone="us-east-1a",
    tags={"Name": "private-subnet"},
)

# Internet Gateway
internet_gateway = aws.ec2.InternetGateway(
    "internet-gateway",
    vpc_id=vpc.id,
    tags={"Name": "internet-gateway"},
)

# Public Route Table
public_route_table = aws.ec2.RouteTable(
    "public-route-table",
    vpc_id=vpc.id,
    routes=[{"cidr_block": "0.0.0.0/0", "gateway_id": internet_gateway.id}],
    tags={"Name": "public-route-table"},
)

# Associate Public Subnet with Route Table
aws.ec2.RouteTableAssociation(
    "public-subnet-association",
    subnet_id=public_subnet.id,
    route_table_id=public_route_table.id,
)

# Security Group for EKS
eks_security_group = aws.ec2.SecurityGroup(
    "eks-sg",
    vpc_id=vpc.id,
    description="EKS security group",
    ingress=[
        {"protocol": "-1", "from_port": 0, "to_port": 0, "cidr_blocks": [vpc.cidr_block]},
    ],
    egress=[
        {"protocol": "-1", "from_port": 0, "to_port": 0, "cidr_blocks": ["0.0.0.0/0"]},
    ],
)

# EKS Cluster Role
eks_role = aws.iam.Role(
    "eks-role",
    assume_role_policy=aws.iam.get_policy_document(
        statements=[
            {
                "actions": ["sts:AssumeRole"],
                "effect": "Allow",
                "principals": [{"type": "Service", "identifiers": ["eks.amazonaws.com"]}],
            }
        ]
    ).json,
)

aws.iam.RolePolicyAttachment(
    "eks-role-AmazonEKSClusterPolicy",
    role=eks_role.id,
    policy_arn="arn:aws:iam::aws:policy/AmazonEKSClusterPolicy",
)

aws.iam.RolePolicyAttachment(
    "eks-role-AmazonEKSVPCResourceController",
    role=eks_role.id,
    policy_arn="arn:aws:iam::aws:policy/AmazonEKSVPCResourceController",
)

# EKS Cluster
eks_cluster = aws.eks.Cluster(
    "eks-cluster",
    role_arn=eks_role.arn,
    vpc_config={
        "subnet_ids": [private_subnet.id, public_subnet.id],
        "security_group_ids": [eks_security_group.id],
    },
    tags={"Name": "eks-cluster"},
)

# Node Group Role
node_group_role = aws.iam.Role(
    "node-group-role",
    assume_role_policy=aws.iam.get_policy_document(
        statements=[
            {
                "actions": ["sts:AssumeRole"],
                "effect": "Allow",
                "principals": [{"type": "Service", "identifiers": ["ec2.amazonaws.com"]}],
            }
        ]
    ).json,
)

aws.iam.RolePolicyAttachment(
    "node-group-role-AmazonEKSWorkerNodePolicy",
    role=node_group_role.id,
    policy_arn="arn:aws:iam::aws:policy/AmazonEKSWorkerNodePolicy",
)

aws.iam.RolePolicyAttachment(
    "node-group-role-AmazonEC2ContainerRegistryReadOnly",
    role=node_group_role.id,
    policy_arn="arn:aws:iam::aws:policy/AmazonEC2ContainerRegistryReadOnly",
)

aws.iam.RolePolicyAttachment(
    "node-group-role-AmazonEKS_CNI_Policy",
    role=node_group_role.id,
    policy_arn="arn:aws:iam::aws:policy/AmazonEKS_CNI_Policy",
)

# Node Group
node_group = aws.eks.NodeGroup(
    "eks-node-group",
    cluster_name=eks_cluster.name,
    node_role_arn=node_group_role.arn,
    subnet_ids=[private_subnet.id],
    scaling_config={
        "desired_size": 3,
        "max_size": 3,
        "min_size": 3,
    },
    tags={"Name": "eks-node-group"},
)

# Load Balancer for EKS
load_balancer = aws.elb.LoadBalancer(
    "eks-load-balancer",
    subnets=[public_subnet.id],
    security_groups=[eks_security_group.id],
    listeners=[
        {
            "instance_port": 80,
            "instance_protocol": "HTTP",
            "lb_port": 80,
            "lb_protocol": "HTTP",
        }
    ],
    tags={"Name": "eks-load-balancer"},
)

# Export Outputs
pulumi.export("vpc_id", vpc.id)
pulumi.export("public_subnet_id", public_subnet.id)
pulumi.export("private_subnet_id", private_subnet.id)
pulumi.export("eks_cluster_name", eks_cluster.name)
pulumi.export("load_balancer_dns", load_balancer.dns_name)