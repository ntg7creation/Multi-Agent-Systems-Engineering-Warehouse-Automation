import { useEffect, useMemo, useState } from 'react'
import TwoDApp from './two_d/App.jsx'
import ThreeDApp from './three_d/App.jsx'
import { getSimulationAdapter } from './simulation/PyodideSimulationAdapter.js'

function routeFromPath(pathname) {
  return pathname.startsWith('/3d') ? '3d' : '2d'
}

function App() {
  const [route, setRoute] = useState(() => routeFromPath(window.location.pathname))
  const [adapterStatus, setAdapterStatus] = useState(() => getSimulationAdapter().getStatus())

  useEffect(() => {
    const handlePopState = () => setRoute(routeFromPath(window.location.pathname))
    window.addEventListener('popstate', handlePopState)
    return () => window.removeEventListener('popstate', handlePopState)
  }, [])

  useEffect(() => getSimulationAdapter().subscribeStatus(setAdapterStatus), [])

  const title = useMemo(() => (
    route === '3d' ? '3D Warehouse Viewer' : '2D Warehouse Simulator'
  ), [route])

  function navigate(nextRoute) {
    const nextPath = nextRoute === '3d' ? '/3d' : '/2d'
    if (window.location.pathname !== nextPath) {
      window.history.pushState({}, '', nextPath)
    }
    setRoute(nextRoute)
  }

  return (
    <div className="vercel-shell">
      <nav className="vercel-nav" aria-label="Warehouse visualization routes">
        <div>
          <strong>Warehouse MAS</strong>
          <span>{title}</span>
        </div>
        <div className="vercel-route-buttons">
          <button
            type="button"
            className={route === '2d' ? 'active' : ''}
            onClick={() => navigate('2d')}
          >
            2D
          </button>
          <button
            type="button"
            className={route === '3d' ? 'active' : ''}
            onClick={() => navigate('3d')}
          >
            3D
          </button>
        </div>
        <span className={`runtime-pill runtime-${adapterStatus.phase}`}>
          {adapterStatus.message}
        </span>
      </nav>
      {route === '3d' ? <ThreeDApp /> : <TwoDApp />}
    </div>
  )
}

export default App
