import logging
import os

from . import consts, prometheus, resources, sh, wait


def setup(project_id: str, name: str, zone: str, version: str,
          service_graph_machine_type: str, service_graph_disk_size_gb: int,
          service_graph_num_nodes: int, client_machine_type: str,
          client_disk_size_gb: int) -> None:
    """Creates and sets up a GKE cluster.

    Args:
        project_id: full ID for the cluster's GCP project
        name: name of the GKE cluster
        zone: GCE zone (e.g. "us-central1-a")
        version: GKE version (e.g. "1.9.7-gke.3")
        service_graph_machine_type: GCE type of service machines
        service_graph_disk_size_gb: disk size of service machines in gigabytes
        service_graph_num_nodes: number of machines in the service graph pool
        client_machine_type: GCE type of client machine
        client_disk_size_gb: disk size of client machine in gigabytes
    """
    sh.run_gcloud(['config', 'set', 'project', project_id], check=True)

    _create_cluster(name, zone, version, 'n1-standard-1', 16, 1)
    _create_cluster_role_binding()

    _create_stackdriver_prometheus(project_id, name, zone)

    _create_service_graph_node_pool(service_graph_num_nodes,
                                    service_graph_machine_type,
                                    service_graph_disk_size_gb)
    _create_client_node_pool(client_machine_type, client_disk_size_gb)


def _create_cluster(name: str, zone: str, version: str, machine_type: str,
                    disk_size_gb: int, num_nodes: int) -> None:
    logging.info('creating cluster "%s"', name)
    sh.run_gcloud(
        [
            'container', 'clusters', 'create', name, '--zone', zone,
            '--cluster-version', version, '--enable-stackdriver-kubernetes',
            '--machine-type', machine_type, '--disk-size',
            str(disk_size_gb), '--num-nodes',
            str(num_nodes)
        ],
        check=True)
    sh.run_gcloud(['config', 'set', 'container/cluster', name], check=True)
    sh.run_gcloud(
        ['container', 'clusters', 'get-credentials', name], check=True)


def _create_service_graph_node_pool(num_nodes: int, machine_type: str,
                                    disk_size_gb: int) -> None:
    logging.info('creating service graph node-pool')
    _create_node_pool(consts.SERVICE_GRAPH_NODE_POOL_NAME, num_nodes,
                      machine_type, disk_size_gb)


def _create_client_node_pool(machine_type: str, disk_size_gb: int) -> None:
    logging.info('creating client node-pool')
    _create_node_pool(consts.CLIENT_NODE_POOL_NAME, 1, machine_type,
                      disk_size_gb)


def _create_node_pool(name: str, num_nodes: int, machine_type: str,
                      disk_size_gb: int) -> None:
    sh.run_gcloud(
        [
            'container', 'node-pools', 'create', name, '--machine-type',
            machine_type, '--num-nodes',
            str(num_nodes), '--disk-size',
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


def _create_stackdriver_prometheus(cluster_project_id: str, cluster_name: str,
                                   cluster_zone: str) -> None:
    prometheus.apply(
        cluster_project_id,
        cluster_name,
        cluster_zone,
        should_reload_config=False)
