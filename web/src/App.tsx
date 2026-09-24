import { useState } from "react"
import { BrowserRouter, Navigate, Route, Routes } from "react-router-dom"
import { Loader2 } from "lucide-react"
import { SidebarInset, SidebarProvider } from "@/components/ui/sidebar"
import { Toaster } from "@/components/ui/sonner"
import { TooltipProvider } from "@/components/ui/tooltip"
import { AppSidebar } from "@/components/app/app-sidebar"
import { SettingsDialog } from "@/components/app/settings"
import { SignIn } from "@/components/app/sign-in"
import { AuthProvider, useAuth } from "@/hooks/use-auth"
import { ContainmentProvider } from "@/hooks/use-containment"
import { ConversationsProvider } from "@/hooks/use-conversations"
import { ChatPage } from "@/pages/chat"
import { PendingPage } from "@/pages/pending"

function Shell() {
  const { user, checking } = useAuth()
  const [settings, setSettings] = useState(false)

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
            <Routes>
              {/* The same element for both, with no key, so React keeps one
                  instance when a new conversation gets its address mid-run.
                  A key here remounted the page, orphaning the live stream and
                  showing an empty conversation while the answer was on its way. */}
              <Route path="/" element={<ChatPage />} />
              <Route path="/c/:id" element={<ChatPage />} />
              <Route path="/knowledge" element={<PendingPage title="Knowledge base" />} />
              <Route path="/admin/users" element={<PendingPage title="Users" />} />
              <Route path="/admin/models" element={<PendingPage title="Models" />} />
              <Route path="/admin/audit" element={<PendingPage title="Audit log" />} />
              <Route path="*" element={<Navigate to="/" replace />} />
            </Routes>
          </SidebarInset>
        </SidebarProvider>
        <SettingsDialog open={settings} onOpenChange={setSettings} />
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
