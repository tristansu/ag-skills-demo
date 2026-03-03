# PR-00000002: Import Agricultural Skills and Oregon Willamette Valley Dataset

| Field               | Value                                                          |
| ------------------- | -------------------------------------------------------------- |
| **PR**              | [Link to PR](#)                                                |
| **Author**          | Clayton Young ([@borealBytes](https://github.com/borealBytes)) |
| **Date**            | 2026-03-03                                                     |
| **Status**          | **Ready to merge**                                             |
| **Branch**          | `skills-import` → `main`                                       |
| **Related issues**  | None                                                           |
| **Deploy strategy** | No deploy needed — data and skills updates                     |

---

## 📋 Summary

### What changed and why

This PR imports agricultural data analysis skills from the `borealBytes/ag-skills` repository and adds a complete Oregon Willamette Valley dataset for analysis.

**Skills Import:**

- Imported 12 AgentSkills.io format skills from `borealBytes/ag-skills` (branch: `skills-content`)
- Skills include: field-boundaries, ssurgo-soil, nasa-power-weather, cdl-cropland, sentinel2-imagery, landsat-imagery, interactive-web-map, eda-explore, eda-visualize, eda-correlate, eda-time-series, eda-compare

**Field-Boundaries Skill Enhancement:**

- Added `pacific_northwest` region with Willamette Valley bounding box (lat 43.5-46.0°N, lon 124.0-121.5°W)
- Added Pacific Northwest crops: wheat, hay, corn, hazelnuts, berries, grapes, grass_seed
- Updated SKILL.md documentation

**Data Setup:**

- Setup Git LFS for `data/` directory via `.gitattributes`
- Downloaded Oregon Willamette Valley agricultural dataset:
  - 50 synthetic field boundaries (GeoJSON)
  - SSURGO soil data (1,198 records from NRCS API)
  - NASA POWER weather data (91,350 daily records, 2020-2024)
  - CDL crop identity (150 records, 2022-2024)

**Agent Integration:**

- Updated `agentic/instructions.md` with Agent Skills auto-discovery guidance
- Agents now automatically discover and apply relevant skills from `.agents/skills/`

---

## 📂 Files Changed

```
.agents/skills/                          # 12 skills, 45 files
.agents/skills/field-boundaries/SKILL.md # Updated with PNW region
.agents/skills/field-boundaries/src/field_boundaries.py  # Added pacific_northwest
agentic/instructions.md                   # Added auto-discovery section
.gitattributes                            # LFS tracking for data/
data/
├── fields_oregon_willamette_2024.geojson
├── soil_oregon_willamette_2024.csv
├── weather_oregon_willamette_2020_2024.csv
├── cdl_oregon_willamette_2022_2024.csv
└── README.md                            # Dataset documentation
```

---

## ✅ Validation

| Check                                | Status                         |
| ------------------------------------ | ------------------------------ |
| Skills format valid (agentskills.io) | ✅ YAML frontmatter + SKILL.md |
| Git LFS tracking                     | ✅ 6 files tracked             |
| Field boundaries download            | ✅ 50 fields                   |
| SSURGO soil API                      | ✅ 1,198 records               |
| NASA POWER API                       | ✅ 91,350 records              |
| CDL download                         | ✅ 150 records                 |
| Documentation                        | ✅ data/README.md updated      |

---

## 🔄 Related Actions

- Skills linked to remote `ag-skills/skills-content` for future updates via `git fetch`
- Data can be regenerated using scripts in skill directories

---

## 📝 Notes

- Field boundaries are synthetic (generated within Willamette Valley bounding box)
- Weather data is real (queried from NASA POWER API)
- Soil data is real (queried from NRCS Soil Data Access API)
- CDL crop data has many unmapped codes due to synthetic field locations
- LFS handles large files; data can be discarded without affecting git history

---

**Last updated:** 2026-03-03
