import click
import json
import requests

@click.group()
def cli():
    pass

@cli.command()
def process():
    response = requests.post('http://localhost:8000/process')
    click.echo(response.json())

@cli.command()
@click.argument('query')
@click.option('--top-k', default=10, type=int)
def search(query, top_k):
    response = requests.get(f'http://localhost:8000/search?query={query}&top_k={top_k}')
    click.echo(json.dumps(response.json(), indent=2))

@cli.command()
@click.argument('id', type=int)
@click.option('--detections', type=str)
@click.option('--description', type=str)
def correct(id, detections, description):
    body = {'detections': json.loads(detections) if detections else None, 'description': description}
    response = requests.post(f'http://localhost:8000/correct/{id}', json=body)
    click.echo(response.json())

if __name__ == '__main__':
    cli()