#!/bin/bash

gunicorn educar_pagina_proyecto.wsgi:application --bind 0.0.0.0:$PORT