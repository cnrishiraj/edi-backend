"use client"

import * as React from "react"

// Simple toast implementation for POC
// In a production app, you'd use something like react-hot-toast or Sonner

interface Toast {
  id: string
  title?: string
  description?: string
  variant?: "default" | "destructive"
}

const toastQueue: Toast[] = []

export function useToast() {
  const toast = React.useCallback(({
    title,
    description,
    variant = "default"
  }: {
    title?: string
    description?: string
    variant?: "default" | "destructive"
  }) => {
    const id = Math.random().toString(36).substr(2, 9)
    const toastData: Toast = { id, title, description, variant }
    
    // Add to queue
    toastQueue.push(toastData)
    
    // Simple console log for POC - in production you'd show actual toast UI
    console.log(`[TOAST ${variant?.toUpperCase()}]${title ? ` ${title}:` : ""} ${description || ""}`)
    
    // Simulate toast display for 3 seconds
    setTimeout(() => {
      const index = toastQueue.findIndex(t => t.id === id)
      if (index > -1) {
        toastQueue.splice(index, 1)
      }
    }, 3000)
    
    return { id }
  }, [])

  return { toast }
}