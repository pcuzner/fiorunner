# fiorunner
API wrapper around fio tool to provide a prometheus endpoint, and job handler

## Introduction
The idea is to provide a fio capability that can be called remotely (like fio client-server), but the call is over http and the service itself provides a /metrics endpoint compatible with prometheus.  

This allows you to run an fio job on bare-metal, or in kubernetes and gather near realtime performance statistics to support visualization with a dashboard. This isn't useful all the time, since fio provides summary stats but when testing disruptive events it can be useful to observe I/O pauses to quantify service impact  

The basic goal is to provide the following;  
- fiorunner service
- sample grafana dashboard

For extra brownie points, a simple cli to drive multiple fiorunners could be added.


## Status
This is still a work-in-progress. The current code establishes the endpoint to start an fio job, receives a job file, syntax checks it, gathers the metrics, but doesn't expose them yet over the /metrics endpoint.
