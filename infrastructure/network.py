import pulumi
import pulumi_aws as aws

# Create a VPC
vpc = aws.ec2.Vpc(
    "vpc",
    cidr_block="10.0.0.0/16",
    enable_dns_hostnames=True,
    enable_dns_support=True
)

# Create Public Subnets in two different AZs
public_subnet_a = aws.ec2.Subnet(
    "public-subnet-a",
    vpc_id=vpc.id,
    cidr_block="10.0.1.0/24",
    map_public_ip_on_launch=True,
    availability_zone="us-east-1a",
    tags={"Name": "public-subnet-a"}
)

public_subnet_b = aws.ec2.Subnet(
    "public-subnet-b",
    vpc_id=vpc.id,
    cidr_block="10.0.2.0/24",
    map_public_ip_on_launch=True,
    availability_zone="us-east-1b",
    tags={"Name": "public-subnet-b"}
)

# Create Private Subnets in two different AZs
private_subnet_a = aws.ec2.Subnet(
    "private-subnet-a",
    vpc_id=vpc.id,
    cidr_block="10.0.10.0/24",
    map_public_ip_on_launch=False,
    availability_zone="us-east-1a",
    tags={"Name": "private-subnet-a", "kubernetes.io/role/internal-elb": "1"}
)

private_subnet_b = aws.ec2.Subnet(
    "private-subnet-b",
    vpc_id=vpc.id,
    cidr_block="10.0.11.0/24",
    map_public_ip_on_launch=False,
    availability_zone="us-east-1b",
    tags={"Name": "private-subnet-b", "kubernetes.io/role/internal-elb": "1"}
)

# Internet Gateway for Public Subnet
igw = aws.ec2.InternetGateway("internet-gateway", vpc_id=vpc.id)

# Route Table for Public Subnet
public_route_table = aws.ec2.RouteTable(
    "public-route-table",
    vpc_id=vpc.id,
    routes=[aws.ec2.RouteTableRouteArgs(
        cidr_block="0.0.0.0/0",
        gateway_id=igw.id
    )]
)

# Associate Public Subnets with Public Route Table
aws.ec2.RouteTableAssociation(
    "public-subnet-a-association",
    route_table_id=public_route_table.id,
    subnet_id=public_subnet_a.id
)

aws.ec2.RouteTableAssociation(
    "public-subnet-b-association",
    route_table_id=public_route_table.id,
    subnet_id=public_subnet_b.id
)

# Create an Elastic IP for NAT Gateway
nat_eip = aws.ec2.Eip("nat-eip", domain="vpc")

# Create NAT Gateway in the Public Subnet
nat_gateway = aws.ec2.NatGateway(
    "nat-gateway",
    subnet_id=public_subnet_a.id,
    allocation_id=nat_eip.id
)

# Route Table for Private Subnet with NAT Gateway
private_route_table = aws.ec2.RouteTable(
    "private-route-table",
    vpc_id=vpc.id,
    routes=[aws.ec2.RouteTableRouteArgs(
        cidr_block="0.0.0.0/0",
        nat_gateway_id=nat_gateway.id
    )]
)

# Associate Private Subnets with Private Route Table
aws.ec2.RouteTableAssociation(
    "private-subnet-a-association",
    route_table_id=private_route_table.id,
    subnet_id=private_subnet_a.id
)

aws.ec2.RouteTableAssociation(
    "private-subnet-b-association",
    route_table_id=private_route_table.id,
    subnet_id=private_subnet_b.id
)

# Export resources
pulumi.export("vpc_id", vpc.id)
pulumi.export("public_subnets", [public_subnet_a.id, public_subnet_b.id])
pulumi.export("private_subnets", [private_subnet_a.id, private_subnet_b.id])