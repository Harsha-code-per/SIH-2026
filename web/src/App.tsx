import { useState } from "react"
import { BrowserRouter, Navigate, Route, Routes, useLocation } from "react-router-dom"
import { Loader2 } from "lucide-react"
import { SidebarInset, SidebarProvider } from "@/components/ui/sidebar"
import { Toaster } from "@/components/ui/sonner"
import { TooltipProvider } from "@/components/ui/tooltip"
import { AppSidebar } from "@/components/app/app-sidebar"
import { CommandPalette } from "@/components/app/command-palette"
import { ErrorBoundary } from "@/components/app/error-boundary"
import { SettingsDialog } from "@/components/app/settings"
import { SignIn } from "@/components/app/sign-in"
import { AuthProvider, useAuth } from "@/hooks/use-auth"
import { ContainmentProvider } from "@/hooks/use-containment"
import { ConversationsProvider } from "@/hooks/use-conversations"
import { ChatPage } from "@/pages/chat"
import { AuditPage } from "@/pages/audit"
import { KnowledgePage } from "@/pages/knowledge"
import { ModelsPage } from "@/pages/models"
import { UsersPage } from "@/pages/users"

function Shell() {
  const { user, checking, can } = useAuth()
  const [settings, setSettings] = useState(false)
  const { pathname } = useLocation()

  if (checking) {
    return (
      <div className="grid min-h-svh place-items-center">
        <Loader2 className="size-5 animate-spin text-muted-foreground" />
      </div>
    )
  }
  if (!user) return <SignIn />

  return (
    <ConversationsProvider>
      <ContainmentProvider>
        <SidebarProvider className="h-svh">
          <AppSidebar onOpenSettings={() => setSettings(true)} />
          <SidebarInset className="min-h-0 overflow-hidden">
            <ErrorBoundary resetKey={pathname}>
            <Routes>
              {/* The same element for both, with no key, so React keeps one
                  instance when a new conversation gets its address mid-run.
                  A key here remounted the page, orphaning the live stream and
                  showing an empty conversation while the answer was on its way. */}
              <Route path="/" element={<ChatPage />} />
              <Route path="/c/:id" element={<ChatPage />} />
              <Route path="/knowledge" element={<KnowledgePage />} />
              {can("manage_users") && <Route path="/admin/users" element={<UsersPage />} />}
              {can("manage_models") && <Route path="/admin/models" element={<ModelsPage />} />}
              {can("read_audit") && <Route path="/admin/audit" element={<AuditPage />} />}
              <Route path="*" element={<Navigate to="/" replace />} />
            </Routes>
            </ErrorBoundary>
          </SidebarInset>
        </SidebarProvider>
        <SettingsDialog open={settings} onOpenChange={setSettings} />
        <CommandPalette onOpenSettings={() => setSettings(true)} />
      </ContainmentProvider>
    </ConversationsProvider>
  )
}

export default function App() {
  return (
    <BrowserRouter>
      <TooltipProvider delayDuration={300}>
        <AuthProvider>
          <Shell />
        </AuthProvider>
        <Toaster position="bottom-right" />
      </TooltipProvider>
    </BrowserRouter>
  )
}
