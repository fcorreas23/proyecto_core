---
title: "Guía rápida de Git y GitHub"
subtitle: "Colaboración en un mismo proyecto con 3 usuarios"
author: "Guía práctica"
date: "Noviembre de 2026"
lang: es
geometry: margin=2.1cm
fontsize: 10pt
mainfont: DejaVu Sans
monofont: DejaVu Sans Mono
colorlinks: true
urlcolor: blue
---

# 1. ¿Qué son Git y GitHub?

**Git** es un sistema de control de versiones que permite registrar los cambios de un proyecto. **GitHub** es una plataforma donde se alojan repositorios Git para compartirlos y colaborar.

| Concepto | Explicación breve |
|---|---|
| Repositorio | Proyecto y su historial de versiones. |
| `main` | Rama principal o estable del proyecto. |
| Rama (*branch*) | Línea de trabajo independiente para una tarea. |
| Commit | Registro de una serie de cambios preparados. |
| Push | Envía commits locales al remoto. |
| Pull | Descarga e integra cambios del remoto en la rama actual. |
| Pull Request (PR) | Solicitud de revisar e integrar una rama en otra. |
| Merge | Integra el historial o cambios de una rama en otra. |

**Idea principal:** Git registra el trabajo en cada computador; GitHub permite compartirlo y revisarlo.

# 2. Escenario: tres integrantes, un repositorio

Supongamos que Ana, Pedro y Francisco desarrollan un proyecto de análisis de datos en Python.

| Persona | Función | Rama sugerida |
|---|---|---|
| Ana | Procesamiento de datos | `feature/procesamiento` |
| Pedro | Visualizaciones | `feature/visualizacion` |
| Francisco | Modelo de clasificación | `feature/modelo` |

```text
proyecto-ciencia-datos (GitHub)
├── main
├── feature/procesamiento
├── feature/visualizacion
└── feature/modelo
```

**Regla del equipo:** nadie desarrolla directamente en `main`. Cada tarea se trabaja en una rama y se incorpora a `main` mediante Pull Request.

# 3. Crear el repositorio y compartirlo

1. Ana entra a GitHub y selecciona **New repository**.
2. Crea `proyecto-ciencia-datos`, marca **Add a README file** y confirma.
3. En **Settings → Collaborators → Add people**, invita a Pedro y Francisco.
4. Pedro y Francisco aceptan la invitación.
5. Cada integrante clona el repositorio usando su propia cuenta y credenciales:

```bash
git clone git@github.com:USUARIO/proyecto-ciencia-datos.git
cd proyecto-ciencia-datos
git remote -v
```

Cambia `USUARIO` por el propietario real. El ejemplo usa SSH: cada persona necesita registrar su clave pública SSH en su cuenta de GitHub. Alternativamente, puede clonar con HTTPS y autenticarse.

**`origin`** es el nombre usual del repositorio remoto asociado al clon.

# 4. Crear ramas y cambiar entre ellas

Primero se actualiza la rama principal. Luego se crea una rama nueva para cada tarea:

```bash
git switch main
git pull origin main
git switch -c feature/modelo
```

Cada integrante sustituye `feature/modelo` por su rama correspondiente. Comandos útiles:

```bash
git branch                  # ramas locales
git branch -a               # ramas locales y remotas
git switch main             # cambiar de rama
git switch feature/modelo   # regresar a la rama de trabajo
```

Para publicar por primera vez la rama en GitHub:

```bash
git push -u origin feature/modelo
```

La opción `-u` configura el seguimiento de la rama remota; después, normalmente basta con `git push`.

# 5. Guardar cambios: status, add, commit y push

Por ejemplo, Francisco crea o modifica `modelo.py`.

```python
def entrenar_modelo(datos):
    print("Entrenando modelo...")
```

Después ejecuta:

```bash
git status
git add modelo.py
git commit -m "feat: implementar entrenamiento del modelo"
git push
```

- **`git status`**: muestra qué cambió.
- **`git add`**: prepara uno o varios archivos para el próximo commit.
- **`git commit`**: registra los cambios preparados en el historial local.
- **`git push`**: publica esos commits en GitHub.

Para preparar todos los cambios del directorio actual puede utilizar `git add .`, pero debe revisar antes con `git status` para no incluir archivos innecesarios o secretos.

# 6. Abrir un Pull Request (PR)

Cuando Francisco termina su funcionalidad:

1. Ejecuta `git push` para subir su rama.
2. Abre el repositorio en GitHub y selecciona **Pull requests → New pull request**.
3. Configura **base: `main`** y **compare: `feature/modelo`**.
4. Escribe un título y un resumen claro de los cambios.
5. Solicita revisión a Ana o Pedro.
6. Una vez resueltas las observaciones y cumplidas las reglas del repositorio, se hace **Merge pull request**.

Ejemplo de descripción:

```text
Título: Implementar modelo de clasificación

- Se agregó modelo.py.
- Se implementó el entrenamiento.
- Se incorporaron pruebas básicas.
```

**¿Qué significa `base` y `compare`?** `base` indica la rama de destino y `compare`, la rama que aporta los cambios.

El PR puede actualizarse: si agregas más commits y los subes a la misma rama, aparecen automáticamente en el PR abierto.

# 7. Actualizar el trabajo después de un merge

Si Ana integró su PR en `main`, los demás deben sincronizar su copia local:

```bash
git switch main
git pull origin main
```

Si Francisco continúa trabajando en `feature/modelo`, puede integrar los cambios recientes de `main`:

```bash
git switch feature/modelo
git merge main
git push
```

**Antes de mezclar ramas:** confirma o guarda temporalmente los cambios sin registrar. Un `merge` puede producir conflictos que requieren revisión.

# 8. ¿Qué es un conflicto y cómo se resuelve?

Sucede cuando Git no puede combinar automáticamente ciertos cambios. Por ejemplo, dos personas editaron de forma incompatible la misma línea de `config.py`:

```text
<<<<<<< HEAD
VERSION = "2.0"
=======
VERSION = "1.1"
>>>>>>> main
```

Para resolver un conflicto durante un **merge**:

1. Abre el archivo en conflicto.
2. Decide la versión correcta o combina ambas.
3. Borra los marcadores `<<<<<<<`, `=======` y `>>>>>>>`.
4. Guarda, prepara el archivo y completa el merge.

```bash
git add config.py
git commit -m "fix: resolver conflicto en configuración"
git push
```

Esto corresponde a un conflicto durante `merge`. Para un `rebase` el proceso termina con `git rebase --continue`, no con el mismo procedimiento.

# 9. Términos adicionales que conviene conocer

| Término | Significado |
|---|---|
| Working directory | Archivos que editas en tu computador. |
| Staging area | Cambios preparados con `git add`. |
| `HEAD` | Referencia al commit actual. |
| `fetch` | Descarga información remota, sin integrarla automáticamente. |
| `clone` | Copia local inicial de un repositorio. |
| `fork` | Copia independiente de un repositorio en GitHub. |
| `rebase` | Reaplica commits sobre una base diferente. |
| `stash` | Guarda temporalmente cambios no confirmados. |
| `revert` | Crea un commit que deshace cambios anteriores. |
| `reset` | Ajusta referencias y, según la opción, cambia archivos o staging. |
| `.gitignore` | Define archivos que Git no debe comenzar a rastrear. |
| Issue | Tarea, mejora o problema registrado en GitHub. |
| Reviewer | Integrante que revisa un PR. |
| Assignee | Responsable de una tarea o Issue. |
| GitHub Actions | Automatización de pruebas y otros procesos. |
| CI/CD | Integración continua y entrega o despliegue continuos. |

**`git fetch` vs. `git pull`:** `fetch` trae referencias y objetos del remoto; `pull` trae e integra esos cambios en la rama actual. Para actualizar `main`, cambia primero a `main`.

# 10. Reglas de colaboración recomendadas

1. Crear una rama por funcionalidad o corrección.
2. Actualizar `main` antes de comenzar una tarea nueva.
3. Hacer commits pequeños, coherentes y descriptivos.
4. Publicar periódicamente la rama para facilitar la revisión.
5. Crear un Pull Request por tarea y pedir revisión a otro integrante.
6. Evitar hacer merge con pruebas fallidas o conflictos pendientes.
7. No compartir contraseñas, tokens ni archivos `.env` que contengan secretos.
8. Mantener `README.md` e instrucciones de ejecución al día.
9. Evitar `git push --force` en ramas compartidas.
10. Eliminar las ramas de tareas terminadas cuando ya no se necesiten.

# 11. Tabla rápida de comandos

| Comando | Para qué sirve |
|---|---|
| `git clone URL` | Clonar un repositorio. |
| `git status` | Revisar el estado del proyecto. |
| `git branch -a` | Ver ramas locales y remotas. |
| `git switch main` | Cambiar a `main`. |
| `git switch -c nueva-rama` | Crear y activar una rama. |
| `git add archivo.py` | Preparar un archivo. |
| `git add .` | Preparar cambios del directorio actual. |
| `git commit -m "mensaje"` | Crear un commit. |
| `git push` | Publicar commits. |
| `git pull origin main` | Integrar `origin/main` en la rama actual. |
| `git fetch origin` | Obtener información remota sin integrar. |
| `git merge main` | Integrar `main` en la rama actual. |
| `git log --oneline` | Ver commits resumidos. |
| `git diff` | Ver cambios sin preparar. |
| `git diff --staged` | Ver cambios preparados. |
| `git stash` | Guardar temporalmente cambios. |
| `git stash pop` | Recuperar cambios guardados. |
| `git branch -d rama` | Eliminar rama local ya integrada. |
| `git remote -v` | Mostrar remotos configurados. |

# 12. Ejercicio: los tres trabajando a la vez

Cada persona ejecuta los comandos en **su propio computador** y en su propio repositorio clonado.

**Ana (procesamiento):**

```bash
git switch main
git pull origin main
git switch -c feature/procesamiento
# Editar archivos de procesamiento
git add .
git commit -m "feat: agregar procesamiento de datos"
git push -u origin feature/procesamiento
```

**Pedro (visualización):**

```bash
git switch main
git pull origin main
git switch -c feature/visualizacion
# Editar archivos de visualización
git add .
git commit -m "feat: agregar visualizaciones"
git push -u origin feature/visualizacion
```

**Francisco (modelo):**

```bash
git switch main
git pull origin main
git switch -c feature/modelo
# Editar archivos del modelo
git add .
git commit -m "feat: agregar modelo de clasificación"
git push -u origin feature/modelo
```

Después, **cada integrante abre un PR distinto**. Si el PR de Ana se integra primero, Francisco y Pedro pueden actualizar `main` y ejecutar `git merge main` desde sus ramas antes de integrar sus propios PR.

# 13. Mensajes de commit claros

Es útil usar la convención *Conventional Commits*:

| Prefijo | Uso | Ejemplo |
|---|---|---|
| `feat` | Nueva funcionalidad | `feat: agregar clasificador` |
| `fix` | Corrección | `fix: corregir cálculo` |
| `docs` | Documentación | `docs: actualizar README` |
| `refactor` | Reorganización del código | `refactor: simplificar funciones` |
| `test` | Pruebas | `test: agregar pruebas unitarias` |
| `chore` | Mantenimiento | `chore: actualizar dependencias` |
| `perf` | Optimización | `perf: acelerar lectura de datos` |

Evita mensajes ambiguos como `cambios` o `arreglos`.

# 14. Flujo diario recomendado

**Comenzar una tarea nueva:**

```bash
git switch main
git pull origin main
git switch -c feature/nueva-funcionalidad
```

**Trabajar y publicar:**

```bash
git status
git add .
git commit -m "feat: agregar nueva funcionalidad"
git push -u origin feature/nueva-funcionalidad
```

**Terminar:** abrir un PR en GitHub, pedir revisión y hacer merge. Después:

```bash
git switch main
git pull origin main
git branch -d feature/nueva-funcionalidad
```

# 15. Errores frecuentes

| Problema | Causa habitual | Qué hacer |
|---|---|---|
| Trabajé directamente en `main` | Olvidé crear rama | Crear ramas antes de desarrollar. |
| `push rejected` | El remoto tiene cambios que faltan localmente | Revisar y sincronizar antes de reenviar. |
| `merge conflict` | Ediciones incompatibles | Resolver manualmente el archivo en conflicto. |
| No aparecen mis cambios en GitHub | Faltó `add`, `commit` o `push` | Revisar `git status` y el historial. |
| No veo cambios de mis compañeros | Rama desactualizada | Actualizar `main` e integrar sus cambios. |

**Precaución:** `git push --force` puede sobrescribir commits de otras personas. `git reset --hard` puede descartar cambios locales: no usar sin entender las consecuencias.

# 16. Resumen y ejercicio final

```text
CLONE → BRANCH → ADD → COMMIT → PUSH → PULL REQUEST
                           ↓
                     REVIEW → MERGE → PULL
```

**Práctica sugerida:** cada persona crea una rama, modifica un archivo distinto, realiza un commit, lo publica y abre un PR para que otro integrante lo revise. Después pueden editar intencionalmente una misma línea en dos ramas para practicar la resolución de conflictos.

**Recursos oficiales:**

- [Git: libro oficial en español](https://git-scm.com/book/es/v2)
- [GitHub: comenzar a usar GitHub](https://docs.github.com/es/get-started/start-your-journey/hello-world)
- [GitHub: documentación de Pull Requests](https://docs.github.com/es/pull-requests)


---

# PARTE II - Git para el desarrollo diario

Ampliación práctica de la guía colaborativa: inspeccionar cambios, volver a una rama, recuperar versiones y deshacer modificaciones con seguridad.

## 17. Entender los tres estados

Working directory: archivos que editas. Staging area: cambios preparados con git add. Repositorio local: commits creados con git commit. GitHub contiene la copia remota que actualizas con git push.

```bash
archivo editado  --git add-->  preparado  --git commit-->  historial
historial local --git push-->  GitHub
```

## 18. Inspeccionar el proyecto: status y diff

```bash
git status
git status -sb
git diff
git diff modelo.py
git diff --staged
git diff HEAD
git diff --stat
git diff --name-only
```

git status muestra la rama y el estado de archivos. git diff muestra cambios sin preparar; git diff --staged muestra lo que entrará en el próximo commit. git diff HEAD compara los cambios rastreados actuales con el último commit.

```bash
Antes:  epochs = 10
Despues: epochs = 100

- epochs = 10
+ epochs = 100
```

## 19. Consultar historial: log, show y blame

```bash
git log
git log --oneline
git log -5 --oneline
git log --oneline --graph --all --decorate
git log --oneline -- modelo.py
git show HEAD
git show a8f23c9
git blame modelo.py
```

git log muestra los commits; --graph permite visualizar ramas y fusiones. git show enseña el contenido de un commit. git blame identifica el último commit que modificó cada línea de un archivo (no necesariamente quién originó un error).

## 20. Cambiar de rama y regresar a la anterior

```bash
git branch --show-current
git switch main
git switch feature/modelo
git switch -
```

git switch - vuelve a la referencia desde la que cambiaste. Si existen cambios locales que serían sobrescritos al cambiar de rama, Git puede impedirlo: primero confirma, guarda temporalmente o descarta los cambios.

## 21. Si no me gustan mis cambios: volver al último commit

CASO A. Modificaste un archivo, pero no hiciste git add:

```bash
git status
git diff
git restore modelo.py
```

git restore modelo.py descarta los cambios NO preparados de ese archivo, devolviéndolo a la versión del área de preparación.

CASO B. Modificaste varios archivos rastreados, pero no hiciste git add:

```bash
git restore .
```

CASO C. Ya ejecutaste git add, pero no hiciste commit:

```bash
git restore --source=HEAD --staged --worktree modelo.py
```

Para restaurar todos los archivos rastreados al último commit, desde la raíz del repositorio:

```bash
git restore --source=HEAD --staged --worktree .
```

CASO D. Restablecer todo el trabajo rastreado de la rama al último commit:

```bash
git reset --hard HEAD
```

> **Importante:** git restore y git reset --hard pueden descartar cambios sin commit de forma irrecuperable. No eliminan normalmente archivos nuevos no rastreados. Antes de usar comandos destructivos, ejecuta git status y git diff.

## 22. Si quiero conservar mis cambios para más adelante: stash

```bash
git stash push -m "Trabajo parcial del modelo"
git stash list
git switch main
# Revisa la otra rama
git switch feature/modelo
git stash pop
```

git stash guarda temporalmente cambios rastreados. git stash apply recupera sin borrar el stash; git stash pop lo elimina si se aplica correctamente. Para incluir archivos nuevos no rastreados, utiliza git stash push -u.

```bash
git stash push -u -m "Trabajo pendiente"
git stash apply
git stash drop stash@{0}
```

## 23. Si ya hice un commit: reset, revert y versiones anteriores

HEAD es el commit actual. HEAD~1 indica el primer antecesor del commit actual. Si el commit es solamente local, reset puede servir para rehacerlo:

```bash
git reset --soft HEAD~1    # Retira commit; cambios preparados
git reset --mixed HEAD~1   # Retira commit; cambios sin preparar
git reset --hard HEAD~1    # Retira commit y descarta cambios
```

Si el commit ya fue compartido con tu equipo, es preferible crear un commit inverso con git revert:

```bash
git revert HEAD
```

Para revisar una versión histórica sin alterar tu rama, o desarrollar desde ella:

```bash
git switch --detach b7d21a4
git switch feature/modelo
git switch -c feature/modelo-alternativo b7d21a4
```

> **Importante:** Evita git reset y git push --force sobre commits compartidos. git revert conserva la historia de trabajo y suele ser más apropiado para ramas colaborativas.

## 24. Recuperar un commit aparentemente perdido: reflog

```bash
git reflog
git switch -c recuperacion HASH_DEL_COMMIT
```

git reflog muestra movimientos locales recientes de HEAD y otras referencias. Puede ayudarte a localizar commits retirados por un reset, mientras sigan disponibles; no garantiza recuperar cambios que nunca fueron confirmados.

## 25. Comparar ramas antes de un Pull Request

```bash
git diff main feature/modelo
git diff main...feature/modelo
git diff --name-only main...feature/modelo
git diff --stat main...feature/modelo
```

La comparación con dos puntos contrasta el estado final de las ramas. Con tres puntos compara el ancestro común con la rama feature/modelo, algo útil para revisar cambios propuestos en un Pull Request.

## 26. Tabla de decisión: qué comando usar

| Necesito... | Comando recomendado |
| --- | --- |
| Revisar archivos modificados | git status |
| Ver exactamente qué cambié | git diff |
| Revisar cambios preparados | git diff --staged |
| Ver commits recientes | git log --oneline |
| Regresar a rama anterior | git switch - |
| Descartar cambios NO preparados | git restore archivo.py |
| Retirar un archivo del staging, sin borrar cambios | git restore --staged archivo.py |
| Descartar TODOS los cambios rastreados sin commit | git reset --hard HEAD |
| Guardar cambios temporalmente | git stash push -m "WIP" |
| Recuperar cambios temporales | git stash pop |
| Rehacer último commit local dejando cambios preparados | git reset --soft HEAD~1 |
| Deshacer un commit compartido | git revert HEAD |
| Examinar una versión previa | git switch --detach HASH |
| Buscar commits perdidos | git reflog |

## 27. Ejercicio seguro en un repositorio de prueba

```bash
mkdir practica-git
cd practica-git
git init
echo "Modelo version 1" > modelo.txt
git add modelo.txt
git commit -m "Crear modelo inicial"
echo "Modelo experimental" > modelo.txt
git status
git diff
git restore modelo.txt
cat modelo.txt
```

El archivo vuelve a decir "Modelo version 1". Ahora prueba guardar y recuperar modificaciones:

```bash
echo "Modelo version 2" > modelo.txt
git stash push -m "Experimento"
cat modelo.txt
git stash pop
cat modelo.txt
```

Al final, el archivo muestra "Modelo version 2". Practica primero en un repositorio de prueba antes de utilizar comandos que descartan cambios en tu proyecto real.

