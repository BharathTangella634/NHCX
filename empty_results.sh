#!/bin/bash
# Nightly script to empty result folders

PROJECT_DIR="/app/NHCX_HACKATHON"

echo "Starting to empty result folders at $(date)"

# Use rm -rf to remove all contents (files and subdirectories) inside the directories, but keep the directories themselves.
rm -rf "$PROJECT_DIR/fhir_results_problem_2"/*
rm -rf "$PROJECT_DIR/nhcx_results_problem_3"/*

echo "Result folders emptied successfully at $(date)"
