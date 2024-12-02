'use server';

import { cookies, headers } from 'next/headers';
import { prisma } from '@/lib/prisma'
import { BoardValue } from '@/types/board';
import { connect } from 'http2';

export async function setUsername(formData: FormData) {
  const username = formData.get('username') as string;
  const userIp = getClientIp();

  // Validate username
  if (!username || username.length < 2) {
    return { error: 'Username must be at least 2 characters long' };
  }

  try {
    // Create user in the db
    const user = await prisma.user.create({
      data: {
        username: username,
        ipAddress: userIp
      }
    });

    // Create a new game in db tied to this user
    const game = await prisma.game.create({
      data: {
        user: {
          connect: { id: user.id }
        }
      }
    })

    const sessionData = {
      username,
      ip: userIp,
      sessionId: user.id,
      gameId: game.id
    };

    // Set cookie using Next.js cookies API
    cookies().set({
      name: "myapp_session",
      value: JSON.stringify(sessionData),
      maxAge: 60 * 60, // 1 hour
      path: '/',
      httpOnly: true,
      secure: process.env.NODE_ENV === "production",
      sameSite: 'strict'
    });

    return { success: true, sessionData };
  } catch (error) {
    console.error('Failed to run query:', error);
    return { 
      error: 'Failed to run query',
      details: error instanceof Error ? error.message : String(error)
    };
  }
}

// Helper to get client IP (mocked for simplicity; adjust for production)
function getClientIp(): string {
  // Retrieve IP address from headers
  const headersList = headers();
  // console.log("headers: ", Object.fromEntries(headersList.entries()))
  
  // Try multiple header sources for IP
  const ipAddress = 
    headersList.get('x-forwarded-for')?.split(',')[0] || 
    headersList.get('x-real-ip') || 
    headersList.get('cf-connecting-ip') || // Cloudflare
    headersList.get('x-cluster-client-ip') || 
    'unknown';

  return ipAddress;
}

export async function clearUsername() {
  cookies().delete('myapp_session');
  return { success: true };
}

export async function recordMove(boardIndex: number, boxIndex: number, turn: number) {
  // Server-side cookie retrieval
  const session = cookies().get('myapp_session')?.value;

  if (session === undefined) {
    console.error("undefined session while trying to recordMove")
    return 
  }

  try {
    // Create the move record
    const userSession = await prisma.move.create({
      data: {
        boardIndex,
        boxIndex,
        turn,
        user: {
          connect: { id: JSON.parse(session).sessionId }
        },
        game: {
          connect: { id: JSON.parse(session).gameId }
        }
      }
    });
  } catch (error) {
    console.error('Failed to create move record:', error);
    return { 
      error: 'Failed to create move record',
      details: error instanceof Error ? error.message : String(error)
    };
  }
}

export async function recordWinner(winner: BoardValue) {
  // Server-side cookie retrieval
  const session = cookies().get('myapp_session')?.value;

  if (session === undefined) {
    console.error("undefined session while trying to recordWinner")
    return 
  }

  try {
    // Create the new game
    const game = await prisma.game.update({
      data: {
        wonAt: new Date(),
        winner: winner,
        user: {
          connect: { id: JSON.parse(session).sessionId }
        }
      },
      where: {
        id: JSON.parse(session).gameId
      }
    });

    const currentSessionData = JSON.parse(session)
    const sessionData = {
      ...currentSessionData,
      gameId: game.id
    };

    // Set cookie using Next.js cookies API
    cookies().set({
      name: "myapp_session",
      value: JSON.stringify(sessionData),
      maxAge: 60 * 60, // 1 hour
      path: '/',
      httpOnly: true,
      secure: process.env.NODE_ENV === "production",
      sameSite: 'strict'
    });

  } catch (error) {
    console.error('Failed to run sql:', error);
    return { 
      error: 'Failed to run sql',
      details: error instanceof Error ? error.message : String(error)
    };
  }
}

export async function newGame() {
  // Server-side cookie retrieval
  const session = cookies().get('myapp_session')?.value;

  if (session === undefined) {
    console.error("undefined session while trying to newGame")
    return 
  }

  try {
    // Create the new game
    const game = await prisma.game.create({
      data: {
        user: {
          connect: { id: JSON.parse(session).sessionId }
        }
      }
    });

    const currentSessionData = JSON.parse(session)
    const sessionData = {
      ...currentSessionData,
      gameId: game.id
    };

    // Set cookie using Next.js cookies API
    cookies().set({
      name: "myapp_session",
      value: JSON.stringify(sessionData),
      maxAge: 60 * 60, // 1 hour
      path: '/',
      httpOnly: true,
      secure: process.env.NODE_ENV === "production",
      sameSite: 'strict'
    });

  } catch (error) {
    console.error('Failed to run sql:', error);
    return { 
      error: 'Failed to run sql',
      details: error instanceof Error ? error.message : String(error)
    };
  }
}