import os

import click

from ..cli import cli_command, STAGES
from ..stacks import StackPlan
from ..rds import RDS, RDSPostgresClient


EXPORT_SNAPSHOT_NAME = "exportdata"
EXPORT_INSTANCE_NAME = "exportdata"
IMPORT_SECURITY_GROUP_NAME = "importdata-sg"


@cli_command('migratedata', max_apps=0)
@click.argument('target_stage', nargs=1, type=click.Choice(STAGES))
@click.argument('target_environment', nargs=1)
@click.argument('target_vars_file', nargs=1)
def migratedata_cmd(ctx, target_stage, target_environment, target_vars_file):
    if target_stage not in ['development', 'preview', 'staging']:
        raise Exception("Invalid target stage [{}]".format(target_stage))

    target_ctx = ctx.new_context(
        stage=target_stage,
        environment=target_environment,
        vars_files=[target_vars_file])

    rds, pg_client = create_scrubbed_instance(ctx, target_stage)
    dump_to_target(target_ctx, pg_client)

    pg_client.close()

    rds.delete_instance(EXPORT_INSTANCE_NAME)
    rds.delete_snapshot(EXPORT_SNAPSHOT_NAME)


def create_scrubbed_instance(ctx, target_stage):
    rds = RDS(ctx.variables['aws_region'], logger=ctx.log, profile_name=ctx.stage)
    plan = StackPlan.from_ctx(ctx, apps=['database'])
    plan.info()

    snapshot = rds.create_new_snapshot(
        EXPORT_SNAPSHOT_NAME,
        rds.get_instance(plan.get_value('stacks.database.outputs')['URL']).id)

    instance = rds.restore_instance_from_snapshot(
        EXPORT_SNAPSHOT_NAME, EXPORT_INSTANCE_NAME,
        dev_user_ips=ctx.variables['dev_user_ips'],
        vpc_id=ctx.variables['vpc_id'])

    pg_client = RDSPostgresClient.from_boto(
        instance,
        ctx.variables['database']['name'],
        ctx.variables['database']['user'],
        ctx.variables['database']['password'],
        logger=ctx.log
    )

    pg_client.clean_database()

    return rds, pg_client


def dump_to_target(ctx, src_pg_client):
    rds = RDS(ctx.variables['aws_region'], logger=ctx.log, profile_name=ctx.stage)
    plan = StackPlan.from_ctx(ctx, apps=['database'])
    plan.info()

    instance = rds.get_instance(plan.get_value('stacks.database.outputs')['URL'])

    instance = rds.allow_access_to_instance(
        instance, IMPORT_SECURITY_GROUP_NAME,
        ctx.variables['dev_user_ips'],
        ctx.variables['vpc_id'])

    pg_client = RDSPostgresClient.from_boto(
        instance,
        ctx.variables['database']['name'],
        ctx.variables['database']['user'],
        ctx.variables['database']['password'],
        logger=ctx.log)

    src_pg_client.dump_to(pg_client)

    pg_client.close()

    sg = rds.get_security_group(IMPORT_SECURITY_GROUP_NAME)
    rds.revoke_access_to_instance(instance, sg)
    rds.delete_security_group(sg)
