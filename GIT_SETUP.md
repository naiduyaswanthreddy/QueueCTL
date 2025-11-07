# Git Setup & Submission Guide

## 📦 Preparing for GitHub Submission

Follow these steps to create a GitHub repository and submit your project.

## Step 1: Initialize Git Repository

```bash
# Navigate to project directory
cd d:\Projects\Flam_QueueCTL

# Initialize git
git init

# Check status
git status
```

## Step 2: Add Files to Git

```bash
# Add all files
git add .

# Verify what will be committed
git status
```

You should see:
- ✅ All Python files
- ✅ Documentation files (README.md, etc.)
- ✅ Test files
- ✅ requirements.txt, setup.py
- ❌ queuectl.db (ignored by .gitignore)
- ❌ __pycache__ (ignored by .gitignore)

## Step 3: Create Initial Commit

```bash
git commit -m "Initial commit: QueueCTL v1.0.0 - Complete implementation

Features:
- CLI-based job queue system
- Multiple worker support with concurrency control
- Automatic retry with exponential backoff
- Dead Letter Queue (DLQ) for failed jobs
- SQLite-based persistence
- Configuration management
- Comprehensive test suite
- Full documentation"
```

## Step 4: Create GitHub Repository

### Option A: Using GitHub Web Interface

1. Go to https://github.com
2. Click "New repository" (+ icon in top right)
3. Fill in details:
   - **Repository name**: `queuectl` or `Flam_QueueCTL`
   - **Description**: `CLI-based background job queue system with retry and DLQ support`
   - **Visibility**: ✅ Public
   - **Initialize**: ❌ Do NOT initialize with README (we already have one)
4. Click "Create repository"

### Option B: Using GitHub CLI (if installed)

```bash
gh repo create queuectl --public --source=. --remote=origin
```

## Step 5: Connect Local to GitHub

After creating the repository on GitHub, you'll see instructions. Use these commands:

```bash
# Add remote
git remote add origin https://github.com/YOUR_USERNAME/queuectl.git

# Verify remote
git remote -v

# Push to GitHub
git branch -M main
git push -u origin main
```

## Step 6: Verify Upload

1. Go to your GitHub repository URL
2. Verify all files are present:
   - ✅ README.md displays on homepage
   - ✅ All source code in `queuectl/` folder
   - ✅ Test files present
   - ✅ Documentation files visible

## Step 7: Create a Release (Optional but Recommended)

```bash
# Create a tag
git tag -a v1.0.0 -m "QueueCTL v1.0.0 - Initial Release"

# Push tag
git push origin v1.0.0
```

Then on GitHub:
1. Go to "Releases"
2. Click "Draft a new release"
3. Select tag `v1.0.0`
4. Title: `QueueCTL v1.0.0`
5. Description: Copy from PROJECT_SUMMARY.md
6. Click "Publish release"

## Step 8: Add Repository Description

On GitHub repository page:
1. Click ⚙️ (Settings icon) next to "About"
2. Add description: `Production-grade CLI job queue with retry, DLQ, and persistence`
3. Add topics: `python`, `cli`, `job-queue`, `background-jobs`, `sqlite`, `retry-mechanism`
4. Save changes

## Step 9: Create Demo Video

### Recording the Demo

**Option A: Use demo.py**
```bash
python demo.py
```
Record your screen while the demo runs.

**Option B: Manual Demo**

Record yourself running these commands:

```bash
# 1. Show help
queuectl --help

# 2. Show configuration
queuectl config show

# 3. Enqueue jobs
queuectl enqueue '{"id":"demo1","command":"echo Hello World"}'
queuectl enqueue '{"id":"demo2","command":"timeout /t 2"}'
queuectl enqueue '{"id":"demo-fail","command":"exit 1","max_retries":2}'

# 4. Check status
queuectl status
queuectl list --state pending

# 5. Start workers
queuectl worker start --count 2
# Let it run for 20 seconds, then Ctrl+C

# 6. Check results
queuectl status
queuectl list --state completed
queuectl dlq list

# 7. Show job details
queuectl info demo-fail

# 8. Retry from DLQ
queuectl dlq retry demo-fail
queuectl info demo-fail
```

### Video Requirements

- **Length**: 3-5 minutes
- **Format**: MP4, AVI, or MOV
- **Quality**: 720p or higher
- **Show**: Terminal with clear text
- **Include**: 
  - Installation/setup
  - Basic job execution
  - Multiple workers
  - Retry mechanism
  - DLQ functionality

### Upload Video

1. **Upload to Google Drive**:
   - Go to https://drive.google.com
   - Upload your video
   - Right-click → Share
   - Change to "Anyone with the link"
   - Copy link

2. **Add to README**:
   ```bash
   # Edit README.md and add at the top:
   ```

   ```markdown
   ## 🎥 Demo Video
   
   Watch the full demonstration: [QueueCTL Demo Video](YOUR_GOOGLE_DRIVE_LINK)
   ```

   ```bash
   # Commit and push
   git add README.md
   git commit -m "Add demo video link"
   git push
   ```

## Step 10: Final Checklist

Before submitting, verify:

- [ ] Repository is public
- [ ] All files are present on GitHub
- [ ] README.md displays correctly
- [ ] Demo video link works
- [ ] Repository has description and topics
- [ ] All documentation is readable
- [ ] .gitignore is working (no .db or __pycache__)
- [ ] License file is present

## Step 11: Submit

Submit your repository URL:
```
https://github.com/YOUR_USERNAME/queuectl
```

## Common Git Commands

### Making Changes After Initial Push

```bash
# Make your changes to files

# Stage changes
git add .

# Commit
git commit -m "Description of changes"

# Push to GitHub
git push
```

### Checking Status

```bash
# See what's changed
git status

# See commit history
git log --oneline

# See what's different
git diff
```

### Undoing Changes

```bash
# Discard changes to a file
git checkout -- filename

# Undo last commit (keep changes)
git reset --soft HEAD~1

# Undo last commit (discard changes)
git reset --hard HEAD~1
```

## Troubleshooting

### Issue: "fatal: remote origin already exists"

```bash
git remote remove origin
git remote add origin https://github.com/YOUR_USERNAME/queuectl.git
```

### Issue: Push rejected

```bash
# Pull first, then push
git pull origin main --rebase
git push
```

### Issue: Large files error

```bash
# Check file sizes
git ls-files -s | awk '{print $4, $2}' | sort -n

# If queuectl.db was accidentally added:
git rm --cached queuectl.db
git commit -m "Remove database file"
git push
```

## Repository Structure on GitHub

Your repository should look like this:

```
queuectl/
├── 📄 README.md                 ← Main page
├── 📄 ARCHITECTURE.md
├── 📄 INSTALLATION.md
├── 📄 CHECKLIST.md
├── 📄 PROJECT_SUMMARY.md
├── 📄 LICENSE
├── 📄 requirements.txt
├── 📄 setup.py
├── 📄 .gitignore
├── 📁 queuectl/
│   ├── __init__.py
│   ├── cli.py
│   ├── database.py
│   ├── models.py
│   ├── queue_manager.py
│   └── worker.py
├── 🧪 test_queuectl.py
├── 🎬 demo.py
├── 📜 quick_test.bat
└── 📜 quick_test.sh
```

## Best Practices

1. **Commit Messages**: Use clear, descriptive messages
2. **Frequent Commits**: Commit logical chunks of work
3. **Test Before Push**: Ensure code works before pushing
4. **Documentation**: Keep README updated
5. **Tags**: Use semantic versioning (v1.0.0, v1.1.0, etc.)

## Additional Resources

- **GitHub Docs**: https://docs.github.com
- **Git Basics**: https://git-scm.com/book/en/v2
- **Markdown Guide**: https://www.markdownguide.org

---

**Ready to submit! 🚀**

Your repository URL will be:
```
https://github.com/YOUR_USERNAME/queuectl
```

Share this link for the assignment submission.
