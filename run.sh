#!/bin/bash
# Levanta el revisor de informes con Docker Compose.
#   ./run.sh          producción: backend (API) + front (nginx) en segundo plano, muestra logs
#   ./run.sh --dev    desarrollo: código montado, recarga automática (uvicorn --reload + vite)
#   ./run.sh --down   para y elimina los contenedores
# Variables: .env.defaults (no secretas, versionado) y .env.secrets (credenciales KAIA, NO versionar;
# ejemplo en .env.default_secrets).

# Change to script directory
cd "$(dirname "$0")"

# Check if docker compose is installed
if ! command -v docker &> /dev/null
then
    echo "Docker could not be found. Please install Docker and try again."
    cd - > /dev/null && exit 1
fi

# Parse command line arguments
while [[ "$#" -gt 0 ]]; do
    case $1 in
        --dev) dev="true"; shift ;;
        --down) down="true"; shift ;;
        *) echo "Unknown parameter passed: $1"; cd - > /dev/null && exit 1 ;;
    esac
done

# Stop potentially running containers (both compose files share the project name)
echo "Stopping containers..."
docker compose -f docker-compose.yml down --remove-orphans 2> /dev/null
docker compose -f dev.docker-compose.yml down --remove-orphans 2> /dev/null

# Check if down flag is set (nothing else to do)
if [ "$down" = "true" ]
then
    cd - > /dev/null && exit
fi

# Data directory (expedientes) lives on the host and is mounted into the backend;
# the backend runs with the host user's uid/gid so the files it writes stay yours.
mkdir -p expedientes
export HOST_UID="$(id -u)" HOST_GID="$(id -g)"

# Check secrets file is present
if [ ! -f ".env.secrets" ]
then
    echo ".env.secrets not found. Please create .env.secrets and try again."
    echo "See .env.default_secrets for an example configuration (KAIA credentials)."
    echo "Be mindful of not committing .env.secrets to version control."
    cd - > /dev/null && exit 1
fi

# Web session credentials must exist; without them nobody can log in (fail closed)
if ! grep -q "^REVISOR_UI_PASSWORD='\?.\+" .env.secrets || ! grep -q "^REVISOR_UI_SESSION_SECRET='\?.\+" .env.secrets
then
    echo "Warning: REVISOR_UI_PASSWORD / REVISOR_UI_SESSION_SECRET missing in .env.secrets."
    echo "The web UI will reject every login until you set them (openssl rand -hex 32 for the secret)."
fi

env_file_arg="--env-file .env.defaults --env-file .env.secrets"

# Run docker compose
if [ "$dev" = "true" ]
then
    echo "Running in development mode."
    command="docker compose $env_file_arg -f dev.docker-compose.yml up --build --remove-orphans"
    echo "$command"
    eval $command
    cd - > /dev/null && exit
else
    echo "Running in production mode."
    command="docker compose $env_file_arg -f docker-compose.yml up --build --remove-orphans -d"
    echo "$command"
    eval $command
    echo "Front en http://localhost:${FRONT_PORT:-8080}  (API detrás de /api)"
    echo "Showing logs (stop reading with Ctrl + C)..."
    docker compose -f docker-compose.yml logs -f
    cd - > /dev/null && exit
fi
