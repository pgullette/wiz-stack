# Wiz Tech Excercise

## Database Server Configuration

[x] Create a Linux EC2 instance on which a database server is installed (e.g., MongoDB).  
[ ] Configure the database with authentication so you can build a database connection string.  
[x] Allow database traffic to originate only from your VPC.  
[x] Configure the database to regularly and automatically back up to your exercise S3 bucket.  
[x] Configure an instance profile to the VM and add the permission `ec2:*` as a custom policy.  
[x] Configure a security group to allow SSH access to the VM from the public internet.  

## Web Application Configuration

[x] Create an EKS cluster instance in the same VPC as your database server.  
[ ] Build and host a container image for your web application.  
[ ] Ensure your built container image contains an arbitrary file called `wizexercise.txt` with some content.  
[ ] Deploy your container-based web application to the EKS cluster.  
[ ] Ensure your web application authenticates to your database server (connection strings are a common approach).  
[ ] Allow public internet traffic to your web application using the service type `LoadBalancer`.  
[ ] Configure your EKS cluster to grant `cluster-admin` privileges to your web application container(s).

## S3 Bucket Configuration

[x] Create an S3 bucket to hold your database backups.  
[x] Configure your bucket such that the public can read and download objects from it.  

## AWS Config

[x] Activate and ensure AWS Config covers your environment.  
[x] Ensure AWS Config detects one or more misconfigurations you can review in your presentation, introducing novel misconfigurations if necessary.  

## Stretch Goals
[ ] Update web-app to show games, moves, players
[ ] Add github action to rebuild and publish container image
[ ] Add github action to deploy built image
[ ] Use local runner with ecr perms via iam role
[ ] Deploy runner, ns, rbac, etc with pulumi
[ ] Create secret with pulumi for db creds
[ ] Use secret during db instance creation
[ ] Mount secret to web app via external-secrets

