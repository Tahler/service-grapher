import contextlib
from typing import Callable, Generator

from . import config, consts, istio as istio_lib


class Environment:
    """Bundles functions to set up, tear down, and interface with a mesh."""

    def __init__(self, name: str, set_up: Callable[[], None],
                 tear_down: Callable[[], None],
                 get_ingress_url: Callable[[], str]) -> None:
        self.name = name
        self.set_up = set_up
        self.tear_down = tear_down
        self.get_ingress_url = get_ingress_url

    @contextlib.contextmanager
    def context(self,
                should_tear_down: bool = True) -> Generator[str, None, None]:
        self.set_up()
        yield self.get_ingress_url()
        if should_tear_down:
            self.tear_down()


def none(entrypoint_service_name: str, entrypoint_service_port: int,
         entrypoint_service_namespace: str) -> Environment:
    def get_ingress_url() -> str:
        return 'http://{}.{}.svc.cluster.local:{}'.format(
            entrypoint_service_name, entrypoint_service_namespace,
            entrypoint_service_port)

    return Environment(
        name='none',
        set_up=_do_nothing,
        tear_down=_do_nothing,
        get_ingress_url=get_ingress_url)


def istio(entrypoint_service_name: str, hub: str, tag: str,
          should_build: bool) -> Environment:
    def set_up() -> None:
        istio_lib.set_up(entrypoint_service_name, hub, tag, should_build)

    return Environment(
        name='istio',
        set_up=set_up,
        tear_down=istio_lib.tear_down,
        get_ingress_url=istio_lib.get_ingress_gateway_url)


def for_state(name: str, entrypoint_service_name: str,
              config: config.RunnerConfig) -> Environment:
    if name == 'NONE':
        env = none(entrypoint_service_name, consts.SERVICE_PORT,
                   consts.SERVICE_GRAPH_NAMESPACE)
    elif name == 'ISTIO':
        env = istio(
            entrypoint_service_name,
            config.istio_hub,
            config.istio_tag,
            should_build=config.should_build_istio)
    else:
        raise ValueError('{} is not a known environment'.format(name))

    return env


def _do_nothing():
    pass
