# LXMF-CLI Plugin Pack

A collection of plugins for [LXMF-CLI](https://github.com/fr33n0w/lxmf-cli).

This repository hosts plugins developed to extend the functionality of LXMF-CLI, a command-line client for the LXMF messaging system built on the Reticulum Network Stack.

## Plugin Installation

Plugins are Python files that must be placed in the `lxmf_client_storage/plugins/` directory of your LXMF-CLI installation.

For instructions on installing, enabling, disabling, and reloading plugins, see the official [LXMF-CLI Plugin System documentation](https://github.com/fr33n0w/lxmf-cli#plugin-management).

## Available Plugins

### Trust Manager

A plugin for managing local contact trust levels, notes, and aliases.

It allows users to classify contacts as trusted, known, or unverified, and maintain additional information about them.

See the [Trust Manager README](trust-manager/README.md) for more information and usage instructions.
