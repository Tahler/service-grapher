import logging
import os

from . import consts, resources, sh


def setup(name: str, zone: str, version: str, machine_type: str,
          disk_size_gb: int, num_nodes: int, client_machine_type: str,
          client_disk_size_gb: int) -> None:
    _create_cluster(name, zone, version, machine_type, disk_size_gb, num_nodes)
    _create_client_node_pool(client_machine_type, client_disk_size_gb)
    _create_cluster_role_binding()
    _create_persistent_volume()
    _initialize_helm()
    _helm_add_prometheus_operator()
    _helm_add_prometheus()


def _create_cluster(name: str, zone: str, version: str, machine_type: str,
                    disk_size_gb: int, num_nodes: int) -> None:
    logging.info('creating cluster "%s"', name)
    sh.run_gcloud(
        [
            'container', 'clusters', 'create', name, '--zone', zone,
            '--cluster-version', version, '--machine-type', machine_type,
            '--disk-size',
            str(disk_size_gb), '--num-nodes',
            str(num_nodes)
        ],
        check=True)
    sh.run_gcloud(
        ['container', 'clusters', 'get-credentials', name], check=True)


def _create_client_node_pool(machine_type: str, disk_size_gb: int) -> None:
    sh.run_gcloud(
        [
            'container', 'node-pools', 'create', consts.CLIENT_NODE_POOL_NAME,
            '--machine-type', machine_type, '--num-nodes=1', '--disk-size',
            str(disk_size_gb)
        ],
        check=True)


def _create_cluster_role_binding() -> None:
    logging.info('creating cluster-admin-binding')
    proc = sh.run_gcloud(['config', 'get-value', 'account'], check=True)
    account = proc.stdout
    sh.run_kubectl(
        [
            'create', 'clusterrolebinding', 'cluster-admin-binding',
            '--clusterrole', 'cluster-admin', '--user', account
        ],
        check=True)


def _create_persistent_volume() -> None:
    logging.info('creating persistent volume')
    sh.run_kubectl(
        ['apply', '-f', resources.PERSISTENT_VOLUME_YAML_PATH], check=True)


def _initialize_helm() -> None:
    logging.info('initializing Helm')
    sh.run_kubectl(
        ['create', '-f', resources.HELM_SERVICE_ACCOUNT_YAML_PATH], check=True)
    sh.run_helm(['init', '--service-account', 'tiller', '--wait'], check=True)
    sh.run_helm(
        [
            'repo', 'add', 'coreos',
            'https://s3-eu-west-1.amazonaws.com/coreos-charts/stable'
        ],
        check=True)


def _helm_add_prometheus_operator() -> None:
    logging.info('installing coreos/prometheus-operator')
    sh.run_helm(
        [
            'install', 'coreos/prometheus-operator', '--name',
            'prometheus-operator', '--namespace', consts.MONITORING_NAMESPACE
        ],
        check=True)


def _helm_add_prometheus() -> None:
    logging.info('installing coreos/prometheus')
    sh.run_helm(
        [
            'install', 'coreos/prometheus', '--name', 'prometheus',
            '--namespace', consts.MONITORING_NAMESPACE, '--values',
            resources.PROMETHEUS_STORAGE_VALUES_YAML_PATH
        ],
        check=True)
