import { Component, type ReactNode } from "react"
import { AlertTriangle } from "lucide-react"
import { Button } from "@/components/ui/button"

/** One component throwing used to blank the whole page -- the palette did,
 *  before its cmdk root was added. Contain it to the view and say so. */
export class ErrorBoundary extends Component<{ children: ReactNode; resetKey?: string },
                                             { error: Error | null }> {
  state = { error: null as Error | null }

  static getDerivedStateFromError(error: Error) { return { error } }

  componentDidUpdate(prev: { resetKey?: string }) {
    // Navigating away is a fresh start.
    if (this.state.error && prev.resetKey !== this.props.resetKey) this.setState({ error: null })
  }

  render() {
    if (!this.state.error) return this.props.children
    return (
      <div className="grid h-full place-items-center p-6">
        <div className="max-w-sm text-center">
          <AlertTriangle className="mx-auto size-6 text-warn" />
          <p className="mt-3 font-medium">This view hit an error.</p>
          <p className="mt-1 break-words text-sm text-muted-foreground">{this.state.error.message}</p>
          <Button variant="outline" size="sm" className="mt-4" onClick={() => location.reload()}>
            Reload
          </Button>
        </div>
      </div>
    )
  }
}
