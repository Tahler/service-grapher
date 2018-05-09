package main

import (
	"fmt"
	"log"
	"net/http"
	"os"

	"github.com/Tahler/service-grapher/pkg/graph"
	yaml "gopkg.in/yaml.v2"
)

const port = 8080

func main() {
	service, err := getServiceFromEnv()
	if err != nil {
		log.Fatal(err)
	}
	handler := serviceHandler{Service: service}
	log.Printf("Listening on port %v\n", port)
	addr := fmt.Sprintf(":%v", port)
	http.ListenAndServe(addr, handler)
}

type serviceHandler struct {
	graph.Service
}

func (h serviceHandler) ServeHTTP(writer http.ResponseWriter, request *http.Request) {
	for _, cmd := range h.Script {
		cmd.Execute()
	}
	log.Printf("Echoing %s to client %s", request.URL.Path, request.RemoteAddr)
	request.Write(writer)
}

func getServiceFromEnv() (service graph.Service, err error) {
	serviceYAML := os.Getenv("SERVICE_YAML")
	log.Printf("Unmarshalling\n%s", serviceYAML)
	err = yaml.Unmarshal([]byte(serviceYAML), &service)
	return
}