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

## [2026-03-02] Task 2: Rewrite mkdocs.yml + Create Custom CSS

### Custom Color Implementation
- Material theme's `primary` field doesn't support arbitrary hex colors directly
- Solution: Set `primary: custom` in theme config, then define CSS variables in extra.css
- CSS Variables override pattern:
  ```css
  :root {
    --md-primary-fg-color: #FFE4E1;  /* Custom color */
    --md-primary-fg-color--light: #FFF0ED;
    --md-primary-fg-color--dark: #E8C4BE;
  }
  ```
- Dark text (#333333) on light background (#FFE4E1) provides sufficient contrast for accessibility

### mkdocs.yml Navigation Structure
- **EXACTLY 6 top-level tabs** required (each starting with `  - ` at column 2)
- Navigation structure verification: Use `sed -n '/^nav:/,/^[a-z]/p' mkdocs.yml | grep -c '^  - '`
- Nested items (Evaluation subitems) use 6-space indentation (3 levels deep):
  ```yaml
  nav:
    - Home: index.md                    # Level 1 (2 spaces)
    - Evaluation:                        # Level 1 (2 spaces)
        - evaluation/index.md            # Level 2 (6 spaces)
        - Broad Utility: ...             # Level 2 (6 spaces)
        - Narrow Utility:                # Level 2 (6 spaces)
            - Overview: ...              # Level 3 (10 spaces)
  ```

### mkdocstrings Plugin Configuration
- `paths: [src]` assumes src/ directory exists in main repo (for API doc generation)
- Plugin configuration in mkdocs.yml:
  ```yaml
  plugins:
    - mkdocstrings:
        handlers:
          python:
            paths: [src]
            options:
              docstring_style: google
              show_source: true
              show_root_heading: true
  ```

### Files Created in Worktree
- `/docs/stylesheets/extra.css`: 517 bytes - Material theme CSS variable overrides
- `/docs/javascripts/mathjax.js`: 267 bytes - MathJax inline/display math configuration
- Rewrote `/mkdocs.yml`: 84 lines - Complete restructure with custom theme and new nav

### Old Navigation Removed
- Removed: Framework section (was at level 1)
- Removed: Resources section (was at level 1)  
- Removed: Computational Resources (was under Evaluation)
- Removed: Predictive Modeling (was under Narrow Utility)
- Verification: `grep -c 'framework\|Resources\|Computational Resources\|Predictive Modeling' mkdocs.yml` returns 0

### Metadata Preserved
From existing mkdocs.yml (lines 1-6):
- site_name: SynOmicBench Documentation
- site_description: Synthetic data benchmarking for omics data
- site_author: SynOmicBench Team
- site_url: https://trinhthechuong.github.io/SynOmicBench/
- repo_url: https://github.com/trinhthechuong/SynOmicBench
- repo_name: SynOmicBench

### Markdown Extensions Preserved
All 11 extensions from original retained:
- admonition, attr_list, md_in_html
- pymdownx.highlight (with pygments)
- pymdownx.inlinehilite, pymdownx.superfences
- pymdownx.tabbed (alternate_style)
- pymdownx.details, pymdownx.arithmatex
- toc (with permalink)

### New Features Added
- MathJax support: Both inline ($...$) and display ($$...$$) math notation
- mkdocstrings: Auto-generates Python API documentation from source
- Material theme features: search.highlight, search.suggest, navigation.top

### Verification Results
✓ `grep 'primary: custom' mkdocs.yml` returns match
✓ `sed -n '/^nav:/,/^[a-z]/p' mkdocs.yml | grep -c '^  - '` returns 6
✓ Old framework/Resources nav removed (grep count = 0)
✓ Custom color #FFE4E1 present in extra.css
✓ All CSS and JS files created in worktree docs/

### Key Insights for Task 3
- mkdocs build will reference stylesheets/extra.css and javascripts/mathjax.js
- Paths in extra_css and extra_javascript are relative to docs_dir (docs/)
- Build will fail if these files don't exist → build verification will catch issues
- No markdown pages need modification in this task; they already have correct frontmatter
