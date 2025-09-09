# Quickstart

### Preflight

Use the `make backup-all` command in the infrastructure repo.   
Download all the backups that you'd like to validate and put them in the `validation_scripts/backups` directory

With the repo on `main` (or whatever the current version is for the backups) run:

```shell
make validate-release-preflight
``` 
This will save the current Statuses and Output Costs for all Analyses for each Backup

### Validate

###### IMPORTANT: The Transaction Pipeline must be running at this point see the note below.

Switch to new branch whose changes you'd like to observe.

Run:

```shell
make validate-release
```

This will validate that all endpoints and compare the statuses and output costs that were saved in the preflight.

Results are written to `validation_scripts/results/` 


----

Note: The Transaction Pipeline must be running for this command to work properly.
Although it’s not directly used in this process, having it active prevents potential errors and warnings in the views.
You can find the repository at: https://github.com/dioptratool/dioptra-service-transaction-pipeline

 Quickstart Guide for the Transaction Pipeline:
 These commands are run in the dioptra-service-transaction-pipeline project root 
 
Build the project:

```shell
make build
make up
```
Generate sample data:

```shell
make gen-test-data
```

Import test the sample data:
```shell
make testimport-transactionscsv
```