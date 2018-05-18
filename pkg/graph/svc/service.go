package svc

import (
	"github.com/Tahler/service-grapher/pkg/graph/pct"
	"github.com/Tahler/service-grapher/pkg/graph/script"
	"github.com/Tahler/service-grapher/pkg/graph/size"
	"github.com/Tahler/service-grapher/pkg/graph/svctype"
)

// Service describes a service in the service graph.
type Service struct {
	// Name is the DNS-addressable name of the service.
	Name string `json:"name"`

	// Type describes what protocol the service supports (e.g. HTTP, gRPC).
	Type svctype.ServiceType `json:"type,omitempty"`

	// ErrorRate is the percentage chance between 0 and 1 that this service
	// should respond with a 500 server error rather than 200 OK.
	ErrorRate pct.Percentage `json:"errorRate,omitempty"`

	// ResponseSize is the number of bytes in the response body.
	ResponseSize size.ByteSize `json:"responseSize,omitempty"`

	// Script is sequentially called each time the service is called.
	Script script.Script `json:"script,omitempty"`
}