---
name: react
description: Capa sobre el plugin react@han: cubre lo que no trae (Vite y sus variables de entorno, claves de lista, StrictMode) y corrige su sesgo hacia memorizar por defecto. Léela junto a las skills del plugin, no en su lugar.
---

# React — huecos y matices

El plugin `react@han` aporta tres skills largas: hooks, context y rendimiento. Cubren bien la superficie de la API. Esta skill **no las repite**: recoge lo que no tratan y dónde conviene leerlas con reservas.

## Hueco: Vite

Ninguna de las tres menciona Vite, que es el empaquetador decidido para este proyecto.

Las variables de entorno **solo llegan al cliente si empiezan por `VITE_`**, y se leen con `import.meta.env.VITE_ALGO`, no con `process.env`. Todo lo que pongas ahí acaba dentro del bundle: **nunca secretos**, ni claves de API, ni cadenas de conexión.

`import.meta.env.DEV` y `.PROD` para ramas por entorno. El proxy de desarrollo va en `vite.config.js` bajo `server.proxy`, y evita los problemas de CORS en local sin tocar el backend.

## Hueco: claves de lista

`key` le dice a React qué elemento es cuál entre renders, y no aparece en las skills del plugin.

Usar el índice del array está bien **solo** si la lista nunca se reordena, filtra ni inserta por el medio. En cuanto lo hace, el estado interno de cada componente se queda pegado a la posición y no al dato: un input escrito acaba apareciendo en la fila de al lado. Usa un id estable del dato; si no existe, genéralo al crear el elemento, nunca al renderizar.

El reverso es útil: cambiar la `key` de un componente lo remonta desde cero. Es la forma idiomática de resetear su estado al cambiar de capítulo o de proyecto, mejor que un `useEffect` que lo limpie a mano.

## Hueco: StrictMode

En desarrollo, React monta, desmonta y vuelve a montar cada componente a propósito, para que los efectos sin limpieza se manifiesten. Si algo "se ejecuta dos veces", el fallo es la limpieza que falta, no StrictMode. Quitarlo esconde el bug hasta producción.

## Matiz: no memorices por defecto

`react-performance` dedica secciones a `React.memo`, `useMemo`, `useCallback`, workers y virtualización. Todo es correcto, pero leído del tirón empuja a memorizar preventivamente, y eso tiene coste propio: más código, más dependencias que mantener sincronizadas, y rara vez una mejora medible.

El orden correcto es perfilar primero con React DevTools, localizar el componente que se renderiza de más, y memorizar ese. Las causas reales de lentitud suelen ser otras tres: listas largas sin virtualizar, un context demasiado ancho, y estado que vive más arriba de lo que necesita.

## Matiz: el mejor efecto es el que no existe

`react-hooks-patterns` enseña `useEffect` a fondo, pero apenas cuándo *no* usarlo. Dos casos que aparecen constantemente:

```jsx
// mal: estado derivado sincronizado con un efecto
const [approved, setApproved] = useState([])
useEffect(() => { setApproved(chapters.filter(c => c.state === 'aprobado')) }, [chapters])

// bien: si se puede calcular, no es estado
const approved = chapters.filter(c => c.state === 'aprobado')
```

`useEffect` es para sincronizar con algo **externo** a React: una suscripción, un intervalo, el título del documento. No para transformar datos para el render, ni para reaccionar a un evento del usuario, que se maneja en el propio manejador.

Y todo efecto que lance una petición la cancela al desmontar:

```jsx
useEffect(() => {
  const ac = new AbortController()
  fetch(url, { signal: ac.signal }).then(...)
  return () => ac.abort()
}, [url])
```

Sin eso, dos peticiones en vuelo pueden resolverse en orden inverso y pintar el resultado viejo sobre el nuevo.

## Detalles que muerden y no salen en el plugin

- `cond && <X/>` pinta un `0` en pantalla si `cond` es numérico. Usa `cond ? <X/> : null`.
- Un input que pasa de `undefined` a un valor cambia de no controlado a controlado y React protesta. Inicializa con `''`.
- `useState(fn)` **ejecuta** `fn` como inicializador perezoso. Para guardar una función como estado, `useState(() => fn)`.
