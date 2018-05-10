package main

import (
	"fmt"
	"log"
	"net/http"

	"github.com/Tahler/service-grapher/pkg/graph"
)

const port = 8080

func main() {
	service, err := getService()
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

func (h serviceHandler) ServeHTTP(
	writer http.ResponseWriter, request *http.Request) {
	var err error
	for _, step := range h.Script {
		exe, err := toExecutable(step)
		if err == nil {
			err = exe.Execute()
			if err != nil {
				log.Println(err)
			}
		} else {
			log.Println(err)
		}
	}
	if err != nil {
		writer.WriteHeader(http.StatusInternalServerError)
	}
	log.Printf("Echoing %s to client %s", request.URL.Path, request.RemoteAddr)
	request.Write(writer)
}
