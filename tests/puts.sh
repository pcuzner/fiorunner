#!/usr/bin/bash

export f=$(cat ../jobs/randrw.job) ; curl -i -H "Content-Type: application/json" -d '{"job": "'"$f"'"}' http://localhost:8081/job -X PUT