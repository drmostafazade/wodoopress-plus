#!/bin/bash
# WodooPress Plus - Git Auto Sync

# Colors
GREEN='\033[0;32m'
YELLOW='\033[1;33m'
NC='\033[0m'

# Function to commit and push
git_sync() {
    echo -e "${YELLOW}🔄 Starting Git sync...${NC}"
    
    # Add all changes
    git add .
    
    # Create commit message
    COMMIT_MSG="$1"
    if [ -z "$COMMIT_MSG" ]; then
        COMMIT_MSG="Auto-sync: $(date '+%Y-%m-%d %H:%M:%S')"
    fi
    
    # Commit
    git commit -m "$COMMIT_MSG"
    
    # Push to GitHub
    git push origin main
    
    echo -e "${GREEN}✅ Git sync completed!${NC}"
    echo -e "${GREEN}📊 Latest commit: $(git log --oneline -1)${NC}"
}

# Run sync
git_sync "$1"
