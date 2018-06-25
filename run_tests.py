#!/usr/bin/env python3

import argparse
import logging

from runner import cluster, config as cfg, resources, pipeline

CLUSTER_NAME = 'isotope-cluster'


def main() -> None:
    args = parse_args()

    log_level = getattr(logging, args.log_level)
    logging.basicConfig(level=log_level, format='%(levelname)s\t> %(message)s')

    config = cfg.from_toml_file(args.config_path)

    if args.create_cluster:
        cluster.setup(CLUSTER_NAME)

    for topology_path in config.topology_paths:
        # TODO: Test cross product of Istio levels and topologies.
        pipeline.run(topology_path)


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser()
    parser.add_argument('config_path', type=str)
    parser.add_argument('--create_cluster', default=False, action='store_true')
    parser.add_argument(
        '--log_level',
        type=str,
        choices=['CRITICAL', 'ERROR', 'WARNING', 'INFO', 'DEBUG'],
        default='INFO')
    return parser.parse_args()


if __name__ == '__main__':
    main()
