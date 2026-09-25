# /// script
# requires-python = ">=3.12"
# dependencies = ["diagrams>=0.24"]
# ///
"""Render docs/architecture.png with AWS icons: `uv run docs/architecture.py` (needs Graphviz)."""

from pathlib import Path

from diagrams import Cluster, Diagram, Edge
from diagrams.aws.compute import ECR, Lambda
from diagrams.aws.general import Client, User
from diagrams.aws.management import CloudwatchLogs
from diagrams.aws.network import APIGateway, CloudFront
from diagrams.aws.storage import SimpleStorageServiceS3Bucket as Bucket

graph = {"splines": "spline", "pad": "0.4", "nodesep": "0.7", "ranksep": "1.1", "fontsize": "22"}

with Diagram(
    "PolyJev on AWS",
    filename=str(Path(__file__).with_name("architecture")),
    outformat="png",
    direction="LR",
    show=False,
    graph_attr=graph,
):
    dev = User("Developer\njust deploy / invoke")
    user = Client("Browser / curl")

    with Cluster("AWS Cloud"):
        ecr = ECR("Amazon ECR\nimages with\nbaked-in weights")
        logs = CloudwatchLogs("CloudWatch Logs")

        with Cluster("Gateway stack  polyjev-gateway"):
            cdn = CloudFront("Amazon CloudFront")
            site = Bucket("S3 site bucket\ndemo app + samples")
            api = APIGateway("API Gateway\nHTTP API\nx-polyjev-token, 5 rps")
            router = Lambda("Router\npolyjev-gateway")
            jobs = Bucket("S3 job bucket\nexpires in 1 day")

        with Cluster("Jev stacks  polyjev-JEV (x15)"):
            fn = Lambda("Container Lambda (arm64)\nhandler -> Jev -> Probs")

    dev >> Edge(label="sam build + push") >> ecr
    ecr >> Edge(label="sam deploy") >> fn
    dev >> Edge(label="aws lambda invoke", style="dashed") >> fn

    user >> cdn
    cdn >> Edge(label="/, /JEV/sample.*") >> site
    cdn >> Edge(label="POST /jevs/JEV\nGET /jobs/ID") >> api
    api >> router
    router >> Edge(label="request / Probs") >> jobs
    router >> Edge(label="async self-invoke,\nthen invoke") >> fn
    [fn, router] >> Edge(style="dotted", label="logs") >> logs
