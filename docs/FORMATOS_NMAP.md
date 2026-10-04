# Formatos de entrada nmap

El parser detecta el formato del fichero y extrae objetivo, puerto, protocolo, estado, servicio y, si está presente, la versión (`-sV`). El formato antiguo de `open_ports.txt` sigue siendo válido.

## Formatos soportados

| Formato | Cómo generarlo | Detección |
|---------|----------------|-----------|
| Normal (`-oN`) | `nmap -sV -oN scan.txt ...` | Texto con `Nmap scan report` |
| Grepable (`-oG`) | `nmap -sV -oG scan.txt ...` | Líneas `Host:` con `Ports:` |
| XML (`-oX`) | `nmap -sV -oX scan.xml ...` | Empieza por `<?xml` o `<nmaprun` |
| Bucle `for` | `echo IP` + `nmap \| grep open` | IP sola y después las líneas de puerto |
| JSON propio | Estructura `{"targets": [...]}` | Empieza por `{` |

Ejemplos en [ejemplos/nmap_outputs/](ejemplos/nmap_outputs/).

## Comandos

```bash
# Normal con versiones
nmap -sV -p- --min-rate 5000 -v 10.19.220.0/24 -oN scan_results.txt

# Grepable
nmap -sV -p- --min-rate 5000 10.19.220.0/24 -oG scan_results.txt

# XML
nmap -sV -p- --min-rate 5000 10.19.220.0/24 -oX scan_results.xml

# Los tres a la vez (-oA escribe .nmap, .gnmap y .xml)
nmap -sV -p- --min-rate 5000 10.19.220.0/24 -oA scan_results

# Varios hosts, un fichero (también soportado)
for i in $(cat hosts.txt); do
  echo "$i"
  nmap -p- --min-rate 5000 -v "$i" | grep open
done > scan_results.txt
```

Pasa el fichero resultante como `input_file` de `audit_start` o `audit_start_and_run`.

## Qué se guarda

Cada puerto queda así:

```json
{
  "port": 22,
  "protocol": "tcp",
  "state": "open",
  "service": "ssh",
  "version": "OpenSSH 7.4"
}
```

`version` es opcional. En XML, un túnel `ssl` o `tls` se antepone al servicio (`ssl/http`), igual que en la salida normal. En grepable, `ssl|http` se normaliza a `ssl/http` para que el perfil elija tareas HTTPS.

## Salida verbosa (`-v`) incompleta

`nmap -v` escribe cada puerto en cuanto lo encuentra:

```
Discovered open port 22/tcp on 192.168.1.1
Discovered open port 80/tcp on 192.168.1.1
```

Esas líneas bastan para crear el target y el puerto, aunque el escaneo no haya terminado y no exista todavía la tabla `PORT STATE SERVICE`. Las líneas `Nmap scan report for ... [host down]` se ignoran.

El servicio queda como `unknown` hasta que aparezca una línea de detalle (`22/tcp open ssh`).

## Bucle for

Cada bloque empieza con una línea que es solo la IP o el hostname. Los puertos que siguen pertenecen a ese objetivo hasta la siguiente IP. Las líneas en blanco entre bloques se ignoran.

```
10.19.220.1
22/tcp open ssh
80/tcp open http

10.19.220.2
443/tcp open https
```

## Límites

- Varios documentos XML pegados en un solo fichero no son XML válido. Usa un `-oX` por ejecución, o el formato normal/grepable si concatenas scans.
- El parser no guarda detección de sistema operativo ni salida de scripts NSE.
- Puertos `closed` o `filtered` que aparezcan en la salida se conservan; `grep open` los deja fuera antes de llegar al parser.
