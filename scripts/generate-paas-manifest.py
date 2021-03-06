#!/usr/bin/env python
# -*- coding: utf-8 -*-

import os
import sys

import click

sys.path.insert(0, '.')  # noqa

from dmaws.utils import load_file, template_string, merge_dicts
from dmaws.variables import load_variables


@click.command()
@click.argument('environment', nargs=1, type=click.Choice(['preview', 'staging', 'production']))
@click.argument('app', nargs=1)
@click.option('--out-file', '-o',
              help="Output file, if empty the template content is printed to the stdout")
@click.option('--vars-file', '-f', multiple=True, type=click.Path(exists=True),
              help="Load YAML or JSON variable file")
def paas_manifest(environment, app, vars_file, out_file):
    """Generate a PaaS manifest file from a Jinja2 template"""

    variables = load_variables(environment, vars_file, {
        'environment': environment,
        'app': app.replace('_', '-')
    })

    template_content = load_file('paas/{}.j2'.format(app))

    variables = merge_dicts(variables, variables[app])

    manifest_content = template_string(template_content, variables, templates_path='paas/')

    if out_file is not None:
        with open(out_file, 'w') as f:
            f.write(manifest_content)
        os.chmod(out_file, 0o600)
    else:
        print(manifest_content)


if __name__ == "__main__":
    paas_manifest()
