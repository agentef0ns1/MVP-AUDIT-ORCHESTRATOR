# Cleanup & Reset Scripts

Herramientas para gestionar, limpiar y resetear proyectos del Audit Orchestrator.

---

## 📋 **Listar Todos los Proyectos**

### **Script: `list_all_projects.py`**

Lista todos los proyectos en la base de datos con estadísticas completas.

```bash
cd /opt/cline-mcps/MVP-audit-orchestrator
python3 scripts/list_all_projects.py
```

**Output de ejemplo:**
```
====================================================================================================
  📊 ALL PROJECTS (2 total)
====================================================================================================

[1] Project: 1787c6f5-5b1d-4ef3-91a8-c6f5103513aa
    Base Path: /home/f0ns1/RedTeam/OCSR25/PoC
    Input File: open_ports.txt
    Status: completed
    Created: 2026-09-30T16:33:32.076971
    Targets: 52 total (pending: 0, completed: 52, failed: 0)
    Findings: 0
    Filesystem: ✅ 52 dirs, 2.04 MB

[2] Project: 2c737090-9fa0-4923-b681-9d11aced51db
    Base Path: /home/f0ns1/RedTeam/OCSR25/PoC
    Input File: open_ports.txt
    Status: running
    Created: 2026-09-30T14:10:18.839125
    Targets: 52 total (pending: 52, completed: 0, failed: 0)
    Findings: 0
    Filesystem: ✅ 52 dirs, 2.04 MB
```

**Información mostrada:**
- ✅ Project ID (para usar en otros scripts)
- ✅ Base path y input file
- ✅ Estado del proyecto
- ✅ Estadísticas de targets (pending, completed, failed)
- ✅ Número de findings
- ✅ Estado del filesystem (existe, tamaño)

---

## 🗑️ **Eliminar un Proyecto Completo**

### **Script: `delete_project_completely.py`**

Elimina un proyecto **completamente**: base de datos **Y** sistema de archivos.

### **Uso Interactivo (con confirmación)**

```bash
python3 scripts/delete_project_completely.py <project_id>
```

**Ejemplo:**
```bash
python3 scripts/delete_project_completely.py 2c737090-9fa0-4923-b681-9d11aced51db
```

**Output:**
```
================================================================================
  🗑️  DELETE PROJECT COMPLETELY
================================================================================

📊 Project Information:
   ID: 2c737090-9fa0-4923-b681-9d11aced51db
   Base Path: /home/f0ns1/RedTeam/OCSR25/PoC
   Input File: open_ports.txt
   Status: running
   Created: 2026-09-30T14:10:18.839125

📈 Will delete:
   Targets: 52
   Findings: 0
   Bitacora entries: 1234

📁 Filesystem:
   Base path exists: /home/f0ns1/RedTeam/OCSR25/PoC
   Target directories: 52
   Examples:
     - 10.19.220.23 (0.05 MB)
     - 10.19.220.25 (0.12 MB)
     ... and 50 more

================================================================================
⚠️  WARNING: This action is IRREVERSIBLE!
================================================================================

This will DELETE:
  ❌ All database records for this project
  ❌ All target directories and files
  ❌ All findings, bitacora, scan results

Type 'DELETE' (in capitals) to confirm: DELETE

================================================================================
  🗑️  DELETING PROJECT...
================================================================================

1️⃣ Deleting from database...
   ✅ Deleted from database:
      - 0 findings
      - 1234 bitacora entries
      - 2262 audit tasks
      - 948 services
      - 52 targets
      - 1 project

2️⃣ Deleting filesystem...
   Deleting: /home/f0ns1/RedTeam/OCSR25/PoC
   ✅ Filesystem deleted

================================================================================
  ✅ PROJECT DELETED SUCCESSFULLY
================================================================================

Project 2c737090-9fa0-4923-b681-9d11aced51db has been completely removed.
Database and filesystem are clean.
```

### **Uso No Interactivo (sin confirmación)**

Para scripts automatizados:

```bash
python3 scripts/delete_project_completely.py <project_id> -y
# o
python3 scripts/delete_project_completely.py <project_id> --yes
```

**⚠️ PELIGRO:** Elimina inmediatamente sin confirmación!

---

## 🔄 **Resetear TODA la Base de Datos**

### **Script: `reset_database_completely.py`**

Elimina **TODOS** los proyectos de la base de datos y opcionalmente todos los archivos.

### **Opción 1: Solo Base de Datos (preservar archivos)**

```bash
python3 scripts/reset_database_completely.py
```

- ✅ Elimina todos los registros de la BD
- ✅ Resetea la BD a estado limpio
- ⚠️ **Preserva** los directorios de proyectos en filesystem

### **Opción 2: Base de Datos + Archivos (limpieza completa)**

```bash
python3 scripts/reset_database_completely.py --delete-files
```

- ✅ Elimina todos los registros de la BD
- ✅ **Elimina todos los directorios** de proyectos
- ✅ Limpieza completa: como recién instalado

**Output de ejemplo:**
```
================================================================================
  🗑️  RESET ENTIRE DATABASE
================================================================================

📊 Current Database Contents:
   Projects: 2
   Targets: 104
   Services: 1896
   Audit Tasks: 4524
   Findings: 0
   Bitacora Entries: 2468

📁 Filesystem:
   Project directories found: 2
     - /home/f0ns1/RedTeam/OCSR25/PoC (2.04 MB)
   Total size: 2.04 MB

================================================================================
⚠️  WARNING: This action is IRREVERSIBLE!
================================================================================

This will:
  ❌ DELETE ALL records from the database
  ❌ RESET the database to empty state
  ❌ DELETE ALL project directories (2 directories)
  ❌ DELETE ALL scan results, findings, logs

Type 'RESET' (in capitals) to confirm: RESET

================================================================================
  🗑️  RESETTING DATABASE...
================================================================================

1️⃣ Deleting database records...
   ✅ Deleted 0 records from findings
   ✅ Deleted 4524 records from audit_tasks
   ✅ Deleted 2468 records from bitacora_entries
   ✅ Deleted 1896 records from services
   ✅ Deleted 104 records from targets
   ✅ Deleted 2 records from projects

   ✅ Database reset complete

2️⃣ Deleting project directories...
   Deleting: /home/f0ns1/RedTeam/OCSR25/PoC
   ✅ Deleted 1 directories

================================================================================
  ✅ RESET COMPLETE
================================================================================

Database: /home/f0ns1/.local/share/audit-orchestrator/audit_state.db
Status: Empty (ready for new projects)
Filesystem: All project directories deleted
```

### **Modo No Interactivo**

```bash
python3 scripts/reset_database_completely.py --delete-files -y
```

---

## 🎯 **Casos de Uso Comunes**

### **Caso 1: Eliminar un proyecto viejo que ya terminó**

```bash
# 1. Listar proyectos
python3 scripts/list_all_projects.py

# 2. Copiar el project_id del que quieres eliminar
# 3. Eliminarlo
python3 scripts/delete_project_completely.py 1787c6f5-5b1d-4ef3-91a8-c6f5103513aa
```

### **Caso 2: Proyecto en estado corrupto, eliminar y recrear**

```bash
# Eliminar proyecto corrupto
python3 scripts/delete_project_completely.py 2c737090-9fa0-4923-b681-9d11aced51db -y

# Recrear desde cero
# (usar audit_start desde MCP client)
```

### **Caso 3: Empezar desde cero completamente**

```bash
# Resetear TODO (BD + archivos)
python3 scripts/reset_database_completely.py --delete-files

# Confirmar con: RESET

# Ahora puedes iniciar proyectos nuevos como si acabaras de instalar
```

### **Caso 4: Múltiples proyectos duplicados en mismo base_path**

```bash
# Listar proyectos
python3 scripts/list_all_projects.py

# Eliminar proyectos duplicados uno por uno
python3 scripts/delete_project_completely.py <project_id_1> -y
python3 scripts/delete_project_completely.py <project_id_2> -y

# O resetear todo si hay muchos
python3 scripts/reset_database_completely.py --delete-files
```

### **Caso 5: Limpiar BD pero mantener archivos para análisis posterior**

```bash
# Reset BD sin eliminar archivos
python3 scripts/reset_database_completely.py

# Los archivos quedan en:
# /home/f0ns1/RedTeam/OCSR25/PoC/10.19.220.*/
```

---

## 📁 **Ubicaciones de Archivos**

### **Base de Datos**
```
~/.local/share/audit-orchestrator/audit_state.db
```

### **Proyectos** (ejemplo)
```
/home/f0ns1/RedTeam/OCSR25/PoC/
├── 10.19.220.23/
│   ├── enumeration/
│   ├── bitacora/
│   └── findings/
├── 10.19.220.25/
│   ├── enumeration/
│   ├── bitacora/
│   └── findings/
└── ...
```

---

## ⚠️ **ADVERTENCIAS IMPORTANTES**

### **1. Acciones Irreversibles**

❌ **Todos estos scripts son IRREVERSIBLES**
- No hay "undo"
- No hay backups automáticos
- Una vez eliminado, se pierde para siempre

### **2. Confirmación Requerida**

Por seguridad, todos los scripts requieren confirmación explícita:
- `delete_project_completely`: Tipear `DELETE`
- `reset_database_completely`: Tipear `RESET`

Para saltear confirmación (scripts automatizados): usar `-y` o `--yes`

### **3. Proyectos con Mismo Base Path**

Si múltiples proyectos comparten el mismo `base_path`:
- Al eliminar el **primer proyecto**: elimina TODO el directorio
- Al eliminar el **segundo proyecto**: no encuentra archivos (ya eliminados)
- Esto es **normal** y esperado

**Solución**: Si quieres mantener archivos de un proyecto, copia el directorio antes de eliminar:
```bash
cp -r /home/f0ns1/RedTeam/OCSR25/PoC /home/f0ns1/RedTeam/OCSR25/PoC.backup
python3 scripts/delete_project_completely.py <project_id>
```

### **4. Permisos de Escritura**

Los scripts necesitan permisos para:
- ✅ Escribir en `~/.local/share/audit-orchestrator/audit_state.db`
- ✅ Eliminar directorios en `base_path` del proyecto

Si obtienes errores de permisos:
```bash
# Verificar permisos BD
ls -la ~/.local/share/audit-orchestrator/audit_state.db

# Verificar permisos proyecto
ls -la /home/f0ns1/RedTeam/OCSR25/PoC

# Si es necesario, ejecutar con permisos adecuados
sudo python3 scripts/...  # Solo si absolutamente necesario
```

---

## 🔍 **Troubleshooting**

### **Error: "Database not found"**

```bash
# Verificar ubicación BD
ls ~/.local/share/audit-orchestrator/audit_state.db

# Si no existe, no hay nada que resetear
# Ejecutar audit_start para crear la BD
```

### **Error: "Project not found"**

```bash
# Listar proyectos disponibles
python3 scripts/list_all_projects.py

# Verificar que el project_id es correcto (copiar/pegar)
```

### **Error: "Permission denied" al eliminar filesystem**

```bash
# Verificar ownership
ls -la /path/to/project/

# Cambiar ownership si es necesario
sudo chown -R $USER:$USER /path/to/project/

# O ejecutar script con sudo (última opción)
sudo python3 scripts/delete_project_completely.py <project_id> -y
```

### **Filesystem eliminado pero BD dice que existe**

Esto puede pasar si alguien borró manualmente los directorios. No es problema:

```bash
# El script detectará que no existe y continuará
python3 scripts/delete_project_completely.py <project_id>

# Output mostrará:
# 2️⃣ Filesystem:
#    ℹ️  Nothing to delete (base path doesn't exist)
```

---

## 📚 **Scripts Relacionados**

| Script | Propósito | Ubicación |
|--------|-----------|-----------|
| `list_all_projects.py` | Listar todos los proyectos | `scripts/` |
| `delete_project_completely.py` | Eliminar un proyecto | `scripts/` |
| `reset_database_completely.py` | Resetear toda la BD | `scripts/` |
| `reset_project.py` | Resetear targets a pending (sin eliminar) | `scripts/` |
| `check_project_status.py` | Ver estado de un proyecto | `scripts/` |

---

## ✅ **Resumen de Comandos**

```bash
# Ver qué proyectos existen
python3 scripts/list_all_projects.py

# Eliminar un proyecto específico
python3 scripts/delete_project_completely.py <project_id>

# Eliminar un proyecto sin confirmación (peligroso!)
python3 scripts/delete_project_completely.py <project_id> -y

# Resetear toda la BD (mantener archivos)
python3 scripts/reset_database_completely.py

# Resetear toda la BD (eliminar archivos también)
python3 scripts/reset_database_completely.py --delete-files

# Resetear sin confirmación (muy peligroso!)
python3 scripts/reset_database_completely.py --delete-files -y
```

---

**💡 Tip:** Antes de resetear, considera usar `reset_project.py` si solo quieres re-ejecutar una auditoría sin perder la estructura:

```bash
python3 scripts/reset_project.py <project_id>
# Resetea targets/services a "pending" sin eliminar nada
```
