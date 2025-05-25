import boto3
import time
import re

def get_non_production_instances(region_name='your-region'):
    ec2_client = boto3.client('ec2', region_name=region_name)
    response = ec2_client.describe_instances(
        Filters=[
            {'Name': 'tag:environment', 'Values': ['non-production']},
            {'Name': 'instance-state-name', 'Values': ['running']}  # ✅ Added filter for running instances
        ]
    )
    instances = []
    for reservation in response['Reservations']:
        for instance in reservation['Instances']:
            instance_id = instance['InstanceId']
            instance_name = next(
                (tag['Value'] for tag in instance.get('Tags', []) if tag['Key'] == 'Name'),
                'Unnamed'
            )
            instances.append({'InstanceId': instance_id, 'InstanceName': instance_name})
    return instances

def get_ssm_managed_instances(region_name='your-region'):
    ssm_client = boto3.client('ssm', region_name=region_name)
    paginator = ssm_client.get_paginator('describe_instance_information')
    managed_instances = []
    for page in paginator.paginate():
        for instance in page['InstanceInformationList']:
            managed_instances.append(instance['InstanceId'])
    return managed_instances

def get_disk_usage(instance_id, instance_name, region_name='your-region'):
    ssm_client = boto3.client('ssm', region_name=region_name)
    try:
        response = ssm_client.send_command(
            InstanceIds=[instance_id],
            DocumentName="AWS-RunShellScript",
            Parameters={'commands': ['df -h /']}
        )
        command_id = response['Command']['CommandId']
        time.sleep(3)  # Sleep to wait for the command to execute

        output = ssm_client.get_command_invocation(
            CommandId=command_id,
            InstanceId=instance_id
        )

        if output['Status'] == 'Success':
            stdout = output['StandardOutputContent']
            match = re.search(r'(\d+)%', stdout)
            if match:
                used_percentage = int(match.group(1))
                if used_percentage > 80:
                    print(f"Instance Name: {instance_name}, Instance ID: {instance_id}, Used Storage: {used_percentage}%")
            else:
                print(f"Instance Name: {instance_name}, Instance ID: {instance_id}, Used Storage: Could not determine.")
        else:
            print(f"Instance Name: {instance_name}, Instance ID: {instance_id}, Command failed with status: {output['Status']}")

    except Exception as e:
        print(f"Error checking instance {instance_name} ({instance_id}): {e}")

def main():
    region = 'ap-south-1'
    instances = get_non_production_instances(region)
    managed_instances = get_ssm_managed_instances(region)

    for instance in instances:
        if instance['InstanceId'] in managed_instances:
            get_disk_usage(instance['InstanceId'], instance['InstanceName'], region)
        else:
            print(f"Skipping instance {instance['InstanceName']} ({instance['InstanceId']}) — Not managed by SSM")

if __name__ == "__main__":
    main()
