package microservices.authz

default allow = false

allowed_calls := {
    "service-orders": {
        "service-auth":    ["GET"],
        "service-payment": ["POST"],
    },
    "service-payment": {
        "service-notification": ["POST"],
        "service-auth":         ["GET"],
    },
    "service-auth": {
        "service-notification": ["POST"],
    },
}

allow if {
    source := input.source_service
    dest   := input.destination_service
    method := input.http_method
    allowed_methods := allowed_calls[source][dest]
    method == allowed_methods[_]
}

violations[msg] if {
    not allow
    msg := sprintf(
        "VIOLATION: %v->%v via %v est non autorise",
        [input.source_service, input.destination_service, input.http_method]
    )
}

compliance_score := 1.0 if {
    count(violations) == 0
}

compliance_score := score if {
    count(violations) > 0
    score := max([0.0, 1.0 - (count(violations) * 0.1)])
}
