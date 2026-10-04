# Documentación - Audit Orchestrator v0.3.0

Índice completo de la documentación del sistema.

---

## 📚 Guías Principales

### 🚀 Inicio Rápido
- **[../README.md](../README.md)** - README principal del proyecto
- **[../QUICK_START.md](../QUICK_START.md)** - Guía de inicio rápido paso a paso
- **[USO_RAPIDO.md](USO_RAPIDO.md)** - Guía de uso rápido en español

### ⚙️ Configuración
- **[../CONFIGURAR_PUERTO_KALI.md](../CONFIGURAR_PUERTO_KALI.md)** - Guía rápida para configurar puerto ⭐
- **[CONFIGURACION.md](CONFIGURACION.md)** - Guía completa de configuración ⭐ **NUEVO**
- **[../.env.example](../.env.example)** - Ejemplo de archivo de variables de entorno
- **[INSTALACION.md](INSTALACION.md)** - Guía de instalación detallada

### 🚀 Funcionalidades Avanzadas
- **[PARALLEL_EXECUTION.md](PARALLEL_EXECUTION.md)** - Ejecución paralela y sistema de revisión ⭐ **NUEVO v0.3.0**
- **[FORMATOS_NMAP.md](FORMATOS_NMAP.md)** - Formatos de entrada nmap (`-oN`, `-oG`, `-oX`, bucle for)
  - 12 ejemplos completos de uso
  - Configuración de concurrencia
  - Sistema de auto-review
  - Detección de fallos automática
  - Reportes por servicios

---

## 🏗️ Arquitectura y Desarrollo

### Arquitectura del Sistema
- **[ARQUITECTURA.md](ARQUITECTURA.md)** - Arquitectura completa del sistema
  - Componentes principales
  - Flujos de ejecución (Type 1, 2, 3)
  - Sistema de ejecución paralela (v0.3.0)
  - Seguridad y validación

### Implementación
- **[IMPLEMENTATION.md](IMPLEMENTATION.md)** - Detalles de implementación
  - Estructura de código
  - Patrones utilizados
  - APIs internas

---

## 🔧 Mantenimiento y Troubleshooting

### Solución de Problemas
- **[TROUBLESHOOTING.md](TROUBLESHOOTING.md)** - Guía de solución de problemas
  - Errores comunes
  - Diagnóstico de problemas
  - Soluciones paso a paso

### Changelog
- **[CHANGELOG.md](CHANGELOG.md)** - Historial completo de cambios
  - **v0.3.0** - Ejecución paralela y sistema de revisión
  - v0.2.5 - Limpieza de documentación
  - v0.2.0 - Detección SSL/HTTPS automática
  - v0.1.0 - Release inicial

---

## 🛠️ Scripts y Herramientas

Todos los scripts están en el directorio `../scripts/`:

### Configuración
- **`configure-kali-port.sh`** ⭐ **NUEVO** - Configurar puerto Kali interactivamente
  ```bash
  ./scripts/configure-kali-port.sh 8080
  ```

### Instalación y Verificación
- **`install.sh`** - Script de instalación completa
- **`verify-fix.sh`** - Verificar instalación y configuración

### Testing
- **`test_runtime_ssl.sh`** - Test de detección SSL/HTTPS
- **`demo_convenience_tools.sh`** - Demo de herramientas de conveniencia

### Desarrollo
- **`regenerate_with_ssl_detection.sh`** - Regenerar perfil con detección SSL

---

## 📊 Características por Versión

### v0.3.0 (2024-10-02) ⭐ **ACTUAL**
- ✅ **Ejecución paralela** (10-20x más rápido)
- ✅ **Sistema de revisión automática** (auto-review)
- ✅ **Detección de auditorías fallidas**
- ✅ **Re-encolado automático**
- ✅ **Reportes por servicios** (SERVICES_REPORT.md)
- ✅ **Configuración completa** (puerto Kali, concurrencia)
- ✅ **Script interactivo de configuración**
- ✅ **Documentación exhaustiva**

### v0.2.5 (2024-10-01)
- ✅ Limpieza de documentación
- ✅ Reorganización de archivos markdown

### v0.2.0 (2024-09-30)
- ✅ Detección automática de SSL/HTTPS
- ✅ Modos de ejecución (Type 1, 2, 3)
- ✅ Integración con LLM

### v0.1.0 (2024-09-15)
- ✅ Release inicial
- ✅ Parser de nmap
- ✅ Sistema de profiles JSON
- ✅ Base de datos SQLite
- ✅ MCP server básico

---

## 🎯 Guías por Caso de Uso

### Para Usuarios Finales
1. [QUICK_START.md](../QUICK_START.md) - Inicio rápido
2. [USO_RAPIDO.md](USO_RAPIDO.md) - Uso básico
3. [CONFIGURAR_PUERTO_KALI.md](../CONFIGURAR_PUERTO_KALI.md) - Configurar puerto
4. [PARALLEL_EXECUTION.md](PARALLEL_EXECUTION.md) - Ejecución paralela

### Para Administradores
1. [INSTALACION.md](INSTALACION.md) - Instalación detallada
2. [CONFIGURACION.md](CONFIGURACION.md) - Configuración completa
3. [TROUBLESHOOTING.md](TROUBLESHOOTING.md) - Solución de problemas

### Para Desarrolladores
1. [ARQUITECTURA.md](ARQUITECTURA.md) - Arquitectura del sistema
2. [IMPLEMENTATION.md](IMPLEMENTATION.md) - Detalles de implementación
3. [CHANGELOG.md](CHANGELOG.md) - Historial de cambios

---

## 🔗 Enlaces Útiles

### Repositorio
- **GitHub**: (pendiente)
- **Issues**: (pendiente)

### Relacionados
- **MCP Kali Server**: Servidor de ejecución de comandos
- **Cursor**: IDE con integración MCP

---

## 📝 Contribuir a la Documentación

Si encuentras errores o quieres mejorar la documentación:

1. Los archivos markdown están en:
   - Raíz: `README.md`, `QUICK_START.md`, `CONFIGURAR_PUERTO_KALI.md`
   - Docs: `docs/*.md`

2. Formato:
   - Markdown estándar
   - Bloques de código con lenguaje especificado
   - Ejemplos prácticos siempre que sea posible

3. Estructura:
   - Títulos claros y descriptivos
   - Ejemplos copy-paste funcionales
   - Links entre documentos relacionados

---

## 📅 Última Actualización

**Versión**: 0.3.0  
**Fecha**: 2026-10-02  
**Principales cambios**: Ejecución paralela, sistema de revisión, configuración completa

---

**¿Necesitas ayuda?** Consulta [TROUBLESHOOTING.md](TROUBLESHOOTING.md) o revisa los ejemplos en [PARALLEL_EXECUTION.md](PARALLEL_EXECUTION.md)
