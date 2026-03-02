## [2026-03-02] Task 1: Install Dependencies & Convert PDFs (CORRECTED)

### CRITICAL LEARNING: Worktree Isolation
**Issue**: Initial implementation created PNG files in main repo instead of worktree
**Root Cause**: Missed that all work must be isolated to worktree (/Users/thechuongtrinh/Workspace/SynOmicBench-docs-work/)
**Resolution**: 
- Removed all 4 PNG files from main repo docs/assets/figures/
- Recreated them in worktree docs/assets/figures/ using absolute source paths
- Verified isolation: main repo has NO task-generated files

**KEY RULE FOR FUTURE TASKS**: 
- All work output MUST go to worktree
- Source files (PDFs, code) can be in main repo
- Use absolute paths when converting between repos
- Final verification: ls worktree/docs/assets/figures/ should show ONLY task-generated files

### Dependencies Installed (Global System)
- **poppler**: v26.02.0_1 via `brew install poppler`
  - pdftocairo available at: /opt/homebrew/bin/pdftocairo
  - Initial timeout issue resolved by extending timeout to 120s
- **mkdocs-material**: v9.7.3 - Documentation theme with dark mode support
- **mkdocstrings**: v1.0.3 - Auto-generates API docs from Python docstrings
- **mkdocstrings-python**: v2.0.3 - Python handler for mkdocstrings

### PDF to PNG Conversions (300 DPI) in Worktree
- **Figure_1_Graphical_abstract.png**: 1.3M (source: main repo manu_md/figures/Figure_1_Graphical_abstract.pdf)
- **processing_pipeline.png**: 3.3M (source: main repo manu_md/figures/processing_pipeline.pdf)
- **melanoma_dge_gcs.png**: 995K (source: main repo Manuscripts/Melanoma/NarrowUtility/DGE/GCS/Seed_42.pdf)
- **melanoma_gsea_pcs.png**: 722K (source: main repo Manuscripts/Melanoma/NarrowUtility/GSEA/PCS/Seed_42.pdf)

### Conversion Pattern (Corrected)
```bash
pdftocairo -png -singlefile -r 300 \
  /Users/thechuongtrinh/Workspace/SynOmicBench/path/to/input.pdf \
  /Users/thechuongtrinh/Workspace/SynOmicBench-docs-work/docs/assets/figures/outputname
```
- Use ABSOLUTE path for source PDF (in main repo)
- Use ABSOLUTE path for output PNG (in worktree)
- This ensures complete isolation and prevents repo contamination

### Key Findings (Post-Fix)
1. **Worktree isolation critical**: All generated files stay in worktree
2. **Main repo remains clean**: No untracked docs/ directory created
3. **Cross-repo operations work**: Absolute paths allow reading from main, writing to worktree
4. **Infrastructure ready**: All mkdocs packages installed system-wide for both repos

### Issues Encountered & Resolved
1. **Initial location error**: PNG files created in main repo instead of worktree
   - Fixed by: removing from main repo, recreating in worktree with absolute paths
   - Prevention: Future tasks MUST verify output location before claiming completion

### Next Steps
- Task 2 can now proceed with mkdocs.yml rewrite in worktree (dependencies installed)
- PNG figures ready for integration into documentation pages in worktree
- All work remains isolated in worktree; main repo unaffected
