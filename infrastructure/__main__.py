import network
import eks
import s3
import ec2
import aws_config
import k8s
import pulumi
from datetime import datetime
from autotag import register_auto_tags

config = pulumi.Config()
tags = config.require_object("tags")
register_auto_tags({
    'user:name': tags.get("user_name"),
    'user:stack_name': tags.get("stack_name"),
    'user:stack-created': datetime.today().strftime('%Y-%m-%d %H:%M:%S'),
})