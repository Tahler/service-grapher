package srv

import (
	"fmt"
	"io/ioutil"

	"github.com/Tahler/isotope/convert/pkg/graph"
	"github.com/Tahler/isotope/convert/pkg/graph/svc"
	"github.com/Tahler/isotope/convert/pkg/graph/svctype"
	"github.com/ghodss/yaml"
	"github.com/fortio/fortio/log"
)

// HandlerFromServiceGraphYAML makes a handler to emulate the service with name
// serviceName in the service graph represented by the YAML file at path.
func HandlerFromServiceGraphYAML(serviceName string, serviceGraph graph.ServiceGraph) (handler Handler, err error) {

	service, err := extractService(serviceGraph, serviceName)
	if err != nil {
		return Handler{}, err
	}
	_ = logService(service)

	serviceTypes := extractServiceTypes(serviceGraph)

	handler = Handler{
		Service:      service,
		ServiceTypes: serviceTypes,
	}
	return handler, nil
}

func logService(service svc.Service) error {
	if log.Log(log.Info) {
		serviceYAML, err := yaml.Marshal(service)
		if err != nil {
			return err
		}
		log.Infof("acting as service %s:\n%s", service.Name, serviceYAML)
	}
	return nil
}

// serviceGraphFromYAMLFile unmarshals the ServiceGraph from the YAML at path.
func serviceGraphFromYAMLFile(path string) (*graph.ServiceGraph, error) {
	var serviceGraph *graph.ServiceGraph

	graphYAML, err := ioutil.ReadFile(path)
	if err != nil {
		return nil, err
	}
	log.Debugf("unmarshalling\n%s", graphYAML)
	err = yaml.Unmarshal(graphYAML, &serviceGraph)
	if err != nil {
		return nil, err
	}
	return serviceGraph, nil
}

// extractService finds the service in serviceGraph with the specified name.
func extractService(serviceGraph graph.ServiceGraph, name string) (svc.Service, error) {
	var service svc.Service

	for _, svc := range serviceGraph.Services {
		if svc.Name == name {
			service = svc
			return service, nil
		}
	}
	err := fmt.Errorf("service with name %s does not exist in %v", name, serviceGraph)
	return svc.Service{}, err
}

// extractServiceTypes builds a map from service name to its type
// (i.e. HTTP or gRPC).
func extractServiceTypes(serviceGraph graph.ServiceGraph) map[string]svctype.ServiceType {
	types := make(map[string]svctype.ServiceType, len(serviceGraph.Services))
	for _, service := range serviceGraph.Services {
		types[service.Name] = service.Type
	}
	return types
}