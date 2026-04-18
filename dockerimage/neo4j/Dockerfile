FROM neo4j:2026.03-community

# Install curl for healthchecks and simple HTTP checks
USER root
RUN apt-get update \
	&& apt-get install -y --no-install-recommends curl \
	&& rm -rf /var/lib/apt/lists/*

RUN mkdir -p /plugins \
	&& curl -fsSL -o /plugins/apoc-2026.03.1-core.jar https://github.com/neo4j/apoc/releases/download/2026.03.1/apoc-2026.03.1-core.jar \
	&& curl -fsSL -o /plugins/neosemantics-5.26.0.jar https://github.com/neo4j-labs/neosemantics/releases/download/5.26.0/neosemantics-5.26.0.jar \
	&& curl -fsSL -o /plugins/neo4j-spatial-5.26.0-server-plugin.jar https://github.com/neo4j-contrib/spatial/releases/download/5.26.0/neo4j-spatial-5.26.0-server-plugin.jar
USER neo4j

COPY conf/apoc.conf /var/lib/neo4j/conf/apoc.conf
COPY conf/neo4j.conf /var/lib/neo4j/conf/neo4j.conf

