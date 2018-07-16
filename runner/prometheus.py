import logging
import time
from typing import Any, Dict, List

import requests
import yaml

from . import consts, md5, kubectl, resources, sh, wait

_STACK_DRIVER_PROMETHEUS_IMAGE = (
    'gcr.io/stackdriver-prometheus/stackdriver-prometheus:release-0.4.2')


def apply(cluster_project_id: str,
          cluster_name: str,
          cluster_zone: str,
          labels: Dict[str, str] = {},
          should_reload_config: bool = True) -> None:
    logging.info('applying Prometheus instance')

    resource_dicts = _get_resource_dicts(cluster_project_id, cluster_name,
                                         cluster_zone, labels)
    kubectl.apply_dicts(
        resource_dicts,
        intermediate_file_path=resources.STACKDRIVER_PROMETHEUS_GEN_YAML_PATH)

    wait.until_deployments_are_ready(consts.STACKDRIVER_NAMESPACE)
    # TODO: This is a hotfix to the reloader not responding for a short time
    # after Prometheus is created.
    if should_reload_config:
        logging.debug('waiting 60 seconds for ConfigMap to propagate')
        # TODO: How to tell that the updated ConfigMap has propagated?
        time.sleep(60)
        _reload_config()


def _reload_config() -> None:
    with kubectl.port_forward(
            'prometheus', 9090,
            namespace=consts.STACKDRIVER_NAMESPACE) as local_port:
        requests.post('http://localhost:{}/-/reload'.format(local_port))


def _get_resource_dicts(cluster_project_id: str, cluster_name: str,
                        cluster_zone: str,
                        labels: Dict[str, str]) -> List[Dict[str, Any]]:
    namespace_dict = {
        'apiVersion': 'v1',
        'kind': 'Namespace',
        'metadata': {
            'name': 'stackdriver',
        },
    }
    cluster_role_dict = {
        'apiVersion':
        'rbac.authorization.k8s.io/v1beta1',
        'kind':
        'ClusterRole',
        'metadata': {
            'name': 'prometheus',
        },
        'rules': [
            {
                'apiGroups': [''],
                'resources': [
                    'nodes',
                    'nodes/proxy',
                    'services',
                    'endpoints',
                    'pods',
                ],
                'verbs': ['get', 'list', 'watch'],
            },
            {
                'apiGroups': ['extensions'],
                'resources': ['ingresses'],
                'verbs': ['get', 'list', 'watch'],
            },
            {
                'nonResourceURLs': ['/metrics'],
                'verbs': ['get'],
            },
        ],
    }
    service_account_dict = {
        'apiVersion': 'v1',
        'kind': 'ServiceAccount',
        'metadata': {
            'name': 'prometheus',
            'namespace': consts.STACKDRIVER_NAMESPACE,
        },
    }
    cluster_role_binding_dict = {
        'apiVersion':
        'rbac.authorization.k8s.io/v1beta1',
        'kind':
        'ClusterRoleBinding',
        'metadata': {
            'name': 'prometheus-stackdriver',
        },
        'roleRef': {
            'apiGroup': 'rbac.authorization.k8s.io',
            'kind': 'ClusterRole',
            'name': 'prometheus',
        },
        'subjects': [{
            'kind': 'ServiceAccount',
            'name': 'prometheus',
            'namespace': consts.STACKDRIVER_NAMESPACE,
        }],
    }
    service_dict = {
        'apiVersion': 'v1',
        'kind': 'Service',
        'metadata': {
            'labels': {
                'name': 'prometheus',
            },
            'name': 'prometheus',
            'namespace': consts.STACKDRIVER_NAMESPACE,
        },
        'spec': {
            'ports': [{
                'name': 'prometheus',
                'port': 9090,
                'protocol': 'TCP',
            }],
            'selector': {
                'app': 'prometheus',
            },
            'type': 'ClusterIP',
        },
    }
    deployment_dict = {
        'apiVersion': 'apps/v1',
        'kind': 'Deployment',
        'metadata': {
            'name': 'prometheus',
            'namespace': consts.STACKDRIVER_NAMESPACE,
        },
        'spec': {
            'replicas': 1,
            'selector': {
                'matchLabels': {
                    'app': 'prometheus',
                },
            },
            'template': {
                'metadata': {
                    'annotations': {
                        'prometheus.io/scrape': 'true',
                    },
                    'labels': {
                        'app': 'prometheus',
                    },
                    'name': 'prometheus',
                    'namespace': consts.STACKDRIVER_NAMESPACE,
                },
                'spec': {
                    'containers': [{
                        'name':
                        'prometheus',
                        'image':
                        _STACK_DRIVER_PROMETHEUS_IMAGE,
                        'imagePullPolicy':
                        'Always',
                        'args': [
                            # Uncomment for verbose logging.
                            '--log.level=debug',
                            # Needed for reloading Prometheus configuration
                            # between tests.
                            '--web.enable-lifecycle',
                            '--config.file=/etc/prometheus/prometheus.yaml',
                        ],
                        'ports': [{
                            'containerPort': 9090,
                            'name': 'web',
                        }],
                        'resources': {
                            'limits': {
                                'cpu': '40m',
                                'memory': '100Mi',
                            },
                            'requests': {
                                'cpu': '20m',
                                'memory': '50Mi',
                            },
                        },
                        'volumeMounts': [{
                            'mountPath': '/etc/prometheus',
                            'name': 'config-volume',
                        }],
                    }],
                    'serviceAccountName':
                    'prometheus',
                    'volumes': [{
                        'configMap': {
                            'name': 'prometheus',
                        },
                        'name': 'config-volume',
                    }],
                },
            },
        },
    }
    config_map_dict = _get_config_map(cluster_project_id, cluster_name,
                                      cluster_zone, labels)
    return [
        namespace_dict,
        cluster_role_dict,
        service_account_dict,
        cluster_role_binding_dict,
        service_dict,
        deployment_dict,
        config_map_dict,
    ]


def _get_config_map(cluster_project_id: str, cluster_name: str,
                    cluster_zone: str,
                    labels: Dict[str, str]) -> Dict[str, Any]:
    """Returns a Kubernetes ConfigMap for stackdriver-prometheus.

    `labels` is appended to all relevant data ingested into stackdriver.

    Other configuration is copied from
    https://cloud.google.com/monitoring/kubernetes-engine/prometheus.
    """
    append_label_configs = [{
        'target_label': key,
        'replacement': value,
    } for key, value in labels.items()]

    # TODO: Stop doing this once Stackdriver's >10 labels issue resolved.
    droppable_istio_labels = [
        'destination_app',
        'destination_namespace',
        'destination_principal',
        # 'destination_service',
        'destination_service_name',
        'destination_service_namespace',
        'destination_version',
        'response_code',
        'source_app',
        'source_namespace',
        'source_version',
        'connection_mtls',
        'destination_workload',
        'destination_workload_namespace',
        'request_protocol',
        'source_principal',
        'source_workload',
        'source_workload_namespace',
        'reporter',
    ]

    drop_istio_label_configs = [{
        'regex': label_key,
        'action': 'labeldrop',
    } for label_key in droppable_istio_labels]

    config = {
        'global': {
            'scrape_interval':
            '{}s'.format(consts.PROMETHEUS_SCRAPE_INTERVAL.seconds),
            'external_labels': {
                '_stackdriver_project_id': cluster_project_id,
                '_kubernetes_cluster_name': cluster_name,
                '_kubernetes_location': cluster_zone,
            },
        },
        'scrape_configs': [
            {
                'job_name':
                'istio-telemetry',
                'kubernetes_sd_configs': [{
                    'role': 'pod',
                    'namespaces': {
                        'names': [
                            consts.ISTIO_NAMESPACE,
                        ],
                    },
                }],
                'relabel_configs': [
                    {
                        'source_labels': ['__meta_kubernetes_namespace'],
                        'regex': consts.ISTIO_NAMESPACE,
                        'action': 'keep',
                    },
                    {
                        'source_labels': ['__meta_kubernetes_pod_label_app'],
                        'regex': 'telemetry',
                        'action': 'keep',
                    },
                    {
                        'source_labels': [
                            '__address__',
                        ],
                        # TODO: Streamline this regex.
                        'regex':
                        '([^:]+)(?::\\d+)?;(\\d+)',
                        # Use port 42422 only for istio-telemetry.
                        'replacement':
                        '$1:{}'.format(consts.ISTIO_TELEMETRY_PORT),
                        'target_label':
                        '__address__',
                        'action':
                        'replace',
                    },
                    *append_label_configs,
                ],
                'metric_relabel_configs':
                drop_istio_label_configs,
            },
            {
                'job_name':
                'kubernetes-nodes',
                'kubernetes_sd_configs': [{
                    'role': 'node',
                    'namespaces': {
                        'names': [
                            consts.DEFAULT_NAMESPACE,
                            consts.SERVICE_GRAPH_NAMESPACE,
                        ],
                    },
                }],
                'scheme':
                'https',
                'relabel_configs': [{
                    'replacement':
                    'kubernetes.default.svc:443',
                    'target_label':
                    '__address__',
                }, {
                    'replacement':
                    '/api/v1/nodes/${1}/proxy/metrics',
                    'source_labels': ['__meta_kubernetes_node_name'],
                    'regex':
                    '(.+)',
                    'target_label':
                    '__metrics_path__',
                }, *append_label_configs],
                'bearer_token_file':
                '/var/run/secrets/kubernetes.io/serviceaccount/token',
                'tls_config': {
                    'ca_file':
                    '/var/run/secrets/kubernetes.io/serviceaccount/ca.crt',
                },
            },
            {
                'job_name':
                'kubernetes-pods-containers',
                'kubernetes_sd_configs': [{
                    'role': 'pod',
                    'namespaces': {
                        'names': [
                            consts.DEFAULT_NAMESPACE,
                            consts.SERVICE_GRAPH_NAMESPACE,
                        ],
                    },
                }],
                'relabel_configs': [{
                    'source_labels':
                    ['__meta_kubernetes_pod_annotation_prometheus_io_scrape'],
                    'regex':
                    True,
                    'action':
                    'keep',
                }, {
                    'source_labels':
                    ['__meta_kubernetes_pod_annotation_prometheus_io_path'],
                    'regex':
                    '(.+)',
                    'target_label':
                    '__metrics_path__',
                    'action':
                    'replace',
                }, {
                    'replacement':
                    '$1:$2',
                    'source_labels': [
                        '__address__',
                        '__meta_kubernetes_pod_annotation_prometheus_io_port'
                    ],
                    'regex':
                    '([^:]+)(?::\\d+)?;(\\d+)',
                    'target_label':
                    '__address__',
                    'action':
                    'replace',
                }, *append_label_configs],
            },
            {
                'job_name':
                'kubernetes-service-endpoints',
                'kubernetes_sd_configs': [{
                    'role': 'endpoints',
                    'namespaces': {
                        'names': [
                            consts.DEFAULT_NAMESPACE,
                            consts.SERVICE_GRAPH_NAMESPACE,
                        ],
                    },
                }],
                'relabel_configs': [{
                    'source_labels': [
                        '__meta_kubernetes_service_annotation_prometheus_io_scrape',
                    ],
                    'regex':
                    True,
                    'action':
                    'keep',
                }, {
                    'source_labels': [
                        '__meta_kubernetes_service_annotation_prometheus_io_scheme',
                    ],
                    'regex':
                    '(https?)',
                    'target_label':
                    '__scheme__',
                    'action':
                    'replace',
                }, {
                    'source_labels': [
                        '__meta_kubernetes_service_annotation_prometheus_io_path',
                    ],
                    'regex':
                    '(.+)',
                    'target_label':
                    '__metrics_path__',
                    'action':
                    'replace',
                }, {
                    'replacement':
                    '$1:$2',
                    'source_labels': [
                        '__address__',
                        '__meta_kubernetes_service_annotation_prometheus_io_port',
                    ],
                    'regex':
                    '([^:]+)(?::\\d+)?;(\\d+)',
                    'target_label':
                    '__address__',
                    'action':
                    'replace',
                }, *append_label_configs],
            },
        ],
        'remote_write': [{
            'queue_config': {
                'capacity': 400,
                'max_samples_per_send': 200,
                'max_shards': 10000,
            },
            'url':
            'https://monitoring.googleapis.com:443/',
            'write_relabel_configs': [{
                'replacement': '',
                'source_labels': ['job'],
                'target_label': 'job',
            }, {
                'replacement': '',
                'source_labels': ['instance'],
                'target_label': 'instance',
            }],
        }],
    }
    config_yaml = yaml.dump(config, default_flow_style=False)
    return {
        'apiVersion': 'v1',
        'kind': 'ConfigMap',
        'metadata': {
            'name': 'prometheus',
            'namespace': consts.STACKDRIVER_NAMESPACE,
        },
        'data': {
            'prometheus.yaml': config_yaml,
        },
    }
