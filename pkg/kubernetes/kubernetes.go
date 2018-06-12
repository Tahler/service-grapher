// Package kubernetes converts service graphs into Kubernetes manifests.
package kubernetes

import (
	"strings"
	"time"

	"github.com/Tahler/service-grapher/pkg/consts"
	"github.com/Tahler/service-grapher/pkg/graph"
	"github.com/Tahler/service-grapher/pkg/graph/svc"
	"github.com/ghodss/yaml"
	appsv1 "k8s.io/api/apps/v1"
	apiv1 "k8s.io/api/core/v1"
	metav1 "k8s.io/apimachinery/pkg/apis/meta/v1"
	"k8s.io/apimachinery/pkg/util/intstr"
)

const (
	// ServiceGraphNamespace is the namespace all service graph related resources
	// (i.e. ConfigMap, Services, and Deployments) will reside in.
	ServiceGraphNamespace = "service-graph"

	numConfigMaps          = 1
	numManifestsPerService = 2

	configMapName = "service-graph-config"
)

var (
	serviceGraphAppLabels  = map[string]string{"app": "service-graph"}
	serviceGraphNodeLabels = map[string]string{"role": "service"}
)

// ServiceGraphToKubernetesManifests converts a ServiceGraph to Kubernetes
// manifests.
func ServiceGraphToKubernetesManifests(
	serviceGraph graph.ServiceGraph) (yamlDoc []byte, err error) {
	numServices := len(serviceGraph.Services)
	numManifests := numManifestsPerService*numServices + numConfigMaps
	manifests := make([]string, 0, numManifests)

	appendManifest := func(manifest interface{}) error {
		yamlDoc, innerErr := yaml.Marshal(manifest)
		if innerErr != nil {
			return innerErr
		}
		manifests = append(manifests, string(yamlDoc))
		return nil
	}

	configMap, err := makeConfigMap(serviceGraph)
	if err != nil {
		return
	}
	err = appendManifest(configMap)
	if err != nil {
		return
	}

	for _, service := range serviceGraph.Services {
		k8sDeployment, err := makeDeployment(service)
		if err != nil {
			return nil, err
		}
		err = appendManifest(k8sDeployment)
		if err != nil {
			return nil, err
		}

		k8sService, err := makeService(service)
		if err != nil {
			return nil, err
		}
		err = appendManifest(k8sService)
		if err != nil {
			return nil, err
		}
	}

	yamlDocString := strings.Join(manifests, "---\n")
	return []byte(yamlDocString), nil
}

func combineLabels(a, b map[string]string) map[string]string {
	c := make(map[string]string, len(a)+len(b))
	for k, v := range a {
		c[k] = v
	}
	for k, v := range b {
		c[k] = v
	}
	return c
}

func makeConfigMap(
	graph graph.ServiceGraph) (configMap apiv1.ConfigMap, err error) {
	configMap.APIVersion = "v1"
	configMap.Kind = "ConfigMap"
	configMap.ObjectMeta.Name = configMapName
	configMap.ObjectMeta.Namespace = ServiceGraphNamespace
	configMap.ObjectMeta.Labels = serviceGraphAppLabels
	timestamp(&configMap.ObjectMeta)

	graphYAMLBytes, err := yaml.Marshal(graph)
	if err != nil {
		return
	}
	configMap.Data = map[string]string{"service-graph": string(graphYAMLBytes)}
	return
}

func makeService(service svc.Service) (k8sService apiv1.Service, err error) {
	k8sService.APIVersion = "v1"
	k8sService.Kind = "Service"
	k8sService.ObjectMeta.Name = service.Name
	k8sService.ObjectMeta.Namespace = ServiceGraphNamespace
	k8sService.ObjectMeta.Labels = serviceGraphAppLabels
	timestamp(&k8sService.ObjectMeta)
	k8sService.Spec.Ports = []apiv1.ServicePort{{Port: consts.ServicePort}}
	k8sService.Spec.Selector = map[string]string{"name": service.Name}
	return
}

func makeDeployment(
	service svc.Service) (k8sDeployment appsv1.Deployment, err error) {
	k8sDeployment.APIVersion = "apps/v1"
	k8sDeployment.Kind = "Deployment"
	k8sDeployment.ObjectMeta.Name = service.Name
	k8sDeployment.ObjectMeta.Namespace = ServiceGraphNamespace
	k8sDeployment.ObjectMeta.Labels = serviceGraphAppLabels
	timestamp(&k8sDeployment.ObjectMeta)
	k8sDeployment.Spec = appsv1.DeploymentSpec{
		Selector: &metav1.LabelSelector{
			MatchLabels: map[string]string{
				"name": service.Name,
			},
		},
		Template: apiv1.PodTemplateSpec{
			ObjectMeta: metav1.ObjectMeta{
				Labels: combineLabels(
					serviceGraphNodeLabels,
					map[string]string{
						"name": service.Name,
					}),
			},
			Spec: apiv1.PodSpec{
				Containers: []apiv1.Container{
					{
						Name:  consts.ServiceContainerName,
						Image: consts.ServiceImageName,
						Env: []apiv1.EnvVar{
							{Name: consts.ServiceNameEnvKey, Value: service.Name},
						},
						VolumeMounts: []apiv1.VolumeMount{
							{
								Name:      "config-volume",
								MountPath: consts.ConfigPath,
							},
						},
						Ports: []apiv1.ContainerPort{
							{
								ContainerPort: consts.ServicePort,
							},
						},
						ReadinessProbe: &apiv1.Probe{
							Handler: apiv1.Handler{
								TCPSocket: &apiv1.TCPSocketAction{
									Port: intstr.FromInt(consts.ServicePort),
								},
							},
							InitialDelaySeconds: 5,
							PeriodSeconds:       10,
						},
					},
				},
				Volumes: []apiv1.Volume{
					{
						Name: "config-volume",
						VolumeSource: apiv1.VolumeSource{
							ConfigMap: &apiv1.ConfigMapVolumeSource{
								LocalObjectReference: apiv1.LocalObjectReference{
									Name: configMapName,
								},
								Items: []apiv1.KeyToPath{
									{
										Key:  consts.ServiceGraphConfigMapKey,
										Path: consts.ServiceGraphYAMLFileName,
									},
								},
							},
						},
					},
				},
			},
		},
	}
	timestamp(&k8sDeployment.Spec.Template.ObjectMeta)
	return
}

func timestamp(objectMeta *metav1.ObjectMeta) {
	objectMeta.CreationTimestamp = metav1.Time{Time: time.Now()}
}
