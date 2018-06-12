package main

import (
	"bytes"
	"fmt"
	"log"
	"net/http"

	"github.com/Tahler/isotope/pkg/consts"
	"github.com/Tahler/isotope/pkg/graph/size"
	"github.com/Tahler/isotope/pkg/graph/svctype"
)

func sendRequest(
	destName string,
	destType svctype.ServiceType,
	size size.ByteSize,
	requestHeader http.Header) (*http.Response, error) {
	url := fmt.Sprintf("http://%s:%v", destName, consts.ServicePort)
	request, err := buildRequest(url, size, requestHeader)
	if err != nil {
		return nil, err
	}
	log.Printf(
		"Sending request to %s (%s)", destName, url)
	return http.DefaultClient.Do(request)
}

func buildRequest(url string, size size.ByteSize, requestHeader http.Header) (
	request *http.Request, err error) {
	payload := make([]byte, size, size)
	request, err = http.NewRequest("GET", url, bytes.NewBuffer(payload))
	if err != nil {
		return
	}
	copyHeader(request, requestHeader)
	return
}

func copyHeader(request *http.Request, header http.Header) {
	for key, values := range header {
		request.Header[key] = values
	}
}
