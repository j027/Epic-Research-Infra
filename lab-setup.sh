#!/bin/bash

# Cybersecurity Lab Environment Setup Script

echo "==========================================="
echo "  Cybersecurity Lab Environment Setup"
echo "==========================================="

# Check if Docker is installed
if ! command -v docker &> /dev/null; then
    echo "❌ Docker is not installed. Please install Docker first."
    exit 1
fi

# Check if Docker Compose is installed
if ! command -v docker-compose &> /dev/null; then
    echo "❌ Docker Compose is not installed. Please install Docker Compose first."
    exit 1
fi

# Check if Docker daemon is running
if ! docker info &> /dev/null; then
    echo "❌ Docker daemon is not running. Please start Docker first."
    exit 1
fi

echo "✅ Docker and Docker Compose are available"

# Function to show usage
show_usage() {
    echo "Usage: $0 [command]"
    echo ""
    echo "Commands:"
    echo "  start   - Build and start the lab environment"
    echo "  stop    - Stop the lab environment"
    echo "  restart - Restart the lab environment"
    echo "  reset   - Reset the environment (removes all data)"
    echo "  status  - Show status of containers"
    echo "  logs    - Show logs from all containers"
    echo "  connect - Connect to Kali jump box via SSH"
    echo ""
}

# Parse command line arguments
case "${1:-start}" in
    start)
        echo "🚀 Building and starting the cybersecurity lab environment..."
        docker-compose up -d --build
        
        if [ $? -eq 0 ]; then
            echo ""
            echo "✅ Lab environment is now running!"
            echo ""
            echo "🔗 Connect to Kali Jump Box:"
            echo "   ssh student@localhost -p 2222"
            echo "   Password: cybersec123"
            echo ""
            echo "🎯 Internal targets:"
            echo "   Ubuntu Target 1: 172.20.0.11"
            echo "   Ubuntu Target 2: 172.20.0.12"
            echo ""
            echo "📚 See README.md for detailed usage instructions"
        else
            echo "❌ Failed to start the environment"
            exit 1
        fi
        ;;
    
    stop)
        echo "🛑 Stopping the lab environment..."
        docker-compose down
        echo "✅ Environment stopped"
        ;;
    
    restart)
        echo "🔄 Restarting the lab environment..."
        docker-compose down
        docker-compose up -d --build
        echo "✅ Environment restarted"
        ;;
    
    reset)
        echo "⚠️  This will completely reset the environment and remove all data."
        read -p "Are you sure? (y/N): " -n 1 -r
        echo
        if [[ $REPLY =~ ^[Yy]$ ]]; then
            echo "🗑️  Resetting environment..."
            docker-compose down -v
            docker system prune -f
            docker-compose up -d --build
            echo "✅ Environment reset complete"
        else
            echo "❌ Reset cancelled"
        fi
        ;;
    
    status)
        echo "📊 Container status:"
        docker-compose ps
        ;;
    
    logs)
        echo "📋 Container logs:"
        docker-compose logs --tail=50
        ;;
    
    connect)
        echo "🔌 Connecting to Kali Jump Box..."
        echo "Password: cybersec123"
        ssh student@localhost -p 2222
        ;;
    
    help|--help|-h)
        show_usage
        ;;
    
    *)
        echo "❌ Unknown command: $1"
        show_usage
        exit 1
        ;;
esac
