# syntax=docker/dockerfile:1
# =============================================================================
# auto-monitor backend (Spring Boot 3.4 / Java 21) - hardened multi-stage image
#  - the JDK + Maven stay in the build stage; production gets a JRE only
# =============================================================================
# ---------- stage 1: build the jar ----------
FROM maven:3.9-eclipse-temurin-21 AS build
WORKDIR /build
COPY pom.xml .
RUN mvn -B -ntp dependency:go-offline
COPY src ./src
RUN mvn -B -ntp package -DskipTests

# ---------- stage 2: runtime ----------
FROM eclipse-temurin:21-jre-alpine AS runtime
LABEL org.opencontainers.image.title="auto-monitor-backend" \
      org.opencontainers.image.description="Spring Boot API of auto-monitor" \
      org.opencontainers.image.licenses="MIT"
RUN apk upgrade --no-cache && addgroup -S app && adduser -S app -G app
WORKDIR /app
COPY --from=build /build/target/*.jar app.jar
USER app
EXPOSE 8080
HEALTHCHECK --interval=30s --timeout=5s --start-period=60s --retries=5 \
  CMD wget -qO- http://127.0.0.1:8080/actuator/health/liveness | grep -q UP || exit 1
ENTRYPOINT ["java", "-XX:MaxRAMPercentage=75", "-jar", "app.jar"]
