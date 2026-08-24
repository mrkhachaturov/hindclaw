load("proxy.in", "proxy")
load("container.in", "container")

app = ace.app(
    "HindClaw Docs",
    routes=[
        ace.proxy("/", proxy.config(container.URL)),
    ],
    container=container.config(container.AUTO),
)
