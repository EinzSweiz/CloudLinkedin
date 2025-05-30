export COMPOSE_DOCKER_CLI_BUILD=1
export DOCKER_BUILDKIT=1

APP_CONTAINER = b2b_linkedin_app_web
DC = docker-compose -f b2b_linkedin_app/docker-compose.yaml
EXEC = docker exec -it

up:
	${DC} up -d

restart:
	${DC} restart

down:
	${DC} down

logs:
	${DC} logs --follow --timestamps --tail=100

attach:
	${DC} up --no-deps --force-recreate --no-build

build:
	${DC} build

rebuild:
	${DC} down && \
	${DC} build --no-cache && \
	${DC} up -d

stop:
	${DC} stop

clean:
	${DC} down --volumes

exec:
	${EXEC} ${APP_CONTAINER} bash

logs-docker:
	docker logs -f --tail=100 ${APP_CONTAINER}

shell:
	${EXEC} ${APP_CONTAINER} python manage.py shell

install:
	pip install -r b2b_linkedin_app/requirements.txt