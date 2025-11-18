#!/bin/bash
# Quick workflow verification script
# This checks if the save workflow is working correctly

echo "=================================================="
echo "Card Annotation Workflow Verification"
echo "=================================================="
echo ""

# Check if gsutil is available
if ! command -v gsutil &> /dev/null; then
    echo "⚠️  gsutil not found. Install Google Cloud SDK:"
    echo "   https://cloud.google.com/sdk/docs/install"
    exit 1
fi

# Check if credentials are configured
echo "1. Checking GCS credentials..."
if [ -f "key.json" ]; then
    echo "   ✅ key.json found"
    BUCKET=$(grep -o '"GCS_BUCKET": "[^"]*"' key.json | cut -d'"' -f4)
    if [ -z "$BUCKET" ]; then
        BUCKET="card_annotation"
    fi
    echo "   Bucket: $BUCKET"
else
    echo "   ⚠️  key.json not found"
    exit 1
fi

# Check bucket access
echo ""
echo "2. Checking bucket access..."
if gsutil ls "gs://$BUCKET" &> /dev/null; then
    echo "   ✅ Can access bucket: $BUCKET"
else
    echo "   ❌ Cannot access bucket: $BUCKET"
    exit 1
fi

# Count files
echo ""
echo "3. Counting files..."
RAW_COUNT=$(gsutil ls "gs://$BUCKET/jsons/*.json" 2>/dev/null | wc -l)
CORR_COUNT=$(gsutil ls "gs://$BUCKET/corrected/*.json" 2>/dev/null | wc -l)
IMG_COUNT=$(gsutil ls "gs://$BUCKET/images/*" 2>/dev/null | wc -l)

echo "   JSON files (raw):       $RAW_COUNT"
echo "   JSON files (corrected): $CORR_COUNT"
echo "   Image files:            $IMG_COUNT"

# Check lock directory
echo ""
echo "4. Checking lock directory..."
if [ -d "data/locks" ]; then
    LOCK_COUNT=$(ls data/locks/*.lock 2>/dev/null | wc -l)
    echo "   ✅ Lock directory exists"
    echo "   Active locks: $LOCK_COUNT"
    if [ "$LOCK_COUNT" -gt 0 ]; then
        echo "   ⚠️  There are active lock files:"
        ls -lh data/locks/*.lock 2>/dev/null | tail -5
    fi
else
    echo "   ⚠️  Lock directory not found (will be created on first run)"
fi

# Check Python dependencies
echo ""
echo "5. Checking Python dependencies..."
python3 -c "import streamlit, google.cloud.storage, portalocker" 2>/dev/null
if [ $? -eq 0 ]; then
    echo "   ✅ All Python dependencies installed"
else
    echo "   ⚠️  Some dependencies missing. Run:"
    echo "      pip install -r requirements.txt"
fi

# Test a sample workflow
echo ""
echo "6. Would you like to test the complete workflow?"
echo "   This will run: python test_workflow.py"
read -p "   Type 'yes' to continue: " response

if [ "$response" = "yes" ]; then
    echo ""
    python3 test_workflow.py
else
    echo "   Skipped workflow test"
fi

echo ""
echo "=================================================="
echo "Verification complete!"
echo ""
echo "Next steps:"
echo "  • Run the app: streamlit run main.py"
echo "  • Run tests: pytest test_utils.py -v"
echo "  • Check logs: tail -f annotation.log"
echo "=================================================="
